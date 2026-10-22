import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
import time
from pathlib import Path

import build_core_package as package
from source_contract import FileSource, TaskHandlers
from unittest.mock import patch


class DistributionTests(unittest.TestCase):
    def test_manifest_rejects_modified_truncated_and_extra_files(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);file=root/'content.txt';file.write_bytes(b'original')
            (root/'manifest.json').write_text(json.dumps({'content.txt':hashlib.sha256(b'original').hexdigest()}))
            self.assertEqual(package.verify_manifest(root),1)
            for content in (b'changed!',b'orig'):
                file.write_bytes(content)
                with self.assertRaises(ValueError):package.verify_manifest(root)
            file.write_bytes(b'original');(root/'unexpected').touch()
            with self.assertRaises(ValueError):package.verify_manifest(root)

    def test_archive_reproducible_across_new_staging_and_source_mtime(self):
        with tempfile.TemporaryDirectory() as temp:
            first=package.build(Path(temp)/'one')
            # copyfile creates new staging mtimes, and a different source mtime must not affect ZIP.
            source=package.ROOT/'distribution/README.md'
            stamp=source.stat()
            try:
                os.utime(source,(stamp.st_atime,stamp.st_mtime-86400))
                second=package.build(Path(temp)/'two')
            finally:os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            self.assertEqual(first['sha256'],second['sha256'])
            self.assertEqual(Path(first['archive']).read_bytes(),Path(second['archive']).read_bytes())
            with zipfile.ZipFile(first['archive']) as archive:
                names=archive.namelist()
                self.assertEqual(names,sorted(names))
                self.assertTrue(all(i.date_time==(1980,1,1,0,0,0) for i in archive.infolist()))

    def test_core_refuses_nonempty_unmarked_data_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sentinel = root/'tasks.sqlite3'
            sentinel.write_bytes(b'foreign-user-content')
            env = {**os.environ, 'SHIWEN_CORE_DATA_DIR':str(root), 'PYTHONDONTWRITEBYTECODE':'1'}
            code = '''
import app_core
from fastapi.testclient import TestClient
try:
    with TestClient(app_core.app): pass
except RuntimeError as exc:
    assert '不能自动迁移已有数据' in str(exc)
else:
    raise AssertionError('foreign data directory was accepted')
'''
            result = subprocess.run([sys.executable,'-B','-c',code],cwd=package.ROOT,env=env,
                                    capture_output=True,text=True,encoding='utf-8',timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(sentinel.read_bytes(),b'foreign-user-content')
            self.assertEqual(sorted(p.name for p in root.iterdir()),['tasks.sqlite3'])

    def test_shared_transcription_can_export_local_provenance_without_url(self):
        from transcript_stage import finish_transcription
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            updates = []
            with patch('transcribe.local_transcribe', return_value={'text':'原话','segments':[]}), patch('media_buffer.state'):
                finish_transcription({'id':'a'*16,'provider':'local'},lambda **v:updates.append(v),root,
                                     root/'audio.wav',1,{'title':'本地讲话','source':{'kind':'local_file','original_name':'讲话.wav'}},
                                     time.perf_counter(),True)
            result = json.loads((root/'transcript.json').read_text(encoding='utf-8'))
            self.assertNotIn('source_url',result)
            self.assertIn('讲话.wav',(root/'transcript.md').read_text(encoding='utf-8'))
            self.assertEqual(updates[-1]['status'],'completed')

    def test_forbidden_gate_all_bytes_paths_hidden_and_utf16(self):
        for name, data in [('.hidden', b'prefix MediaCrawler suffix'),
                           ('image.bin', b'\x00DOUYIN\xff'),
                           ('ok.txt', 'MediaCrawler'.encode('utf-16le')),
                           ('douyin/ok', b'clean')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                p = Path(temp)/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                with self.assertRaises(ValueError):
                    package.verify(temp)

    def test_source_contract_and_explicit_dispatch(self):
        source = FileSource(original_name='讲话.mp3', sha256='a'*64, size_bytes=100)
        handlers = TaskHandlers()
        self.assertIsNone(handlers.resolve({'url': 'https://example.com'}))
        handler = object()
        handlers.register('local_file', handler)
        self.assertIs(handlers.resolve({'source': source.model_dump()}), handler)
        with self.assertRaises(ValueError):
            handlers.register('local_file', handler)
        for field in ({'size_bytes': 1_000_000_001}, {'sha256': 'invalid'}, {'source_url': 'https://example.com'}):
            with self.assertRaises(ValueError):
                FileSource(**{**source.model_dump(), **field})

    def test_artifact_boots_without_private_workspace_and_preserves_unknown_tasks(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact = package.build(Path(temp)/'output')
            root = Path(temp)/'standalone'
            with zipfile.ZipFile(artifact['archive']) as z:
                z.extractall(root)
            self.assertEqual(package.verify(root), artifact['files'])
            self.assertFalse((root/'data').exists())
            env = {k:v for k,v in os.environ.items() if k not in
                   {'PYTHONPATH', 'SHIWEN_DATA_DIR', 'SHIWEN_CORE_DATA_DIR', 'SHIWEN_PROFILE',
                    'SILICONFLOW_API_KEY', 'DEEPSEEK_API_KEY'}}
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            script = r'''
import sys, json
import app_core, store, documents
from fastapi.testclient import TestClient
assert store.DATA.name == 'data-core'
store.init()
store.DATA.joinpath('.core-profile').write_text('core-v1',encoding='utf-8')
record={'id':'aaaaaaaaaaaaaaaa','source':{'kind':'unknown'},'status':'running','created_at':1,'title':'unknown'}
store.save(record)
before=store.get(record['id'])
with TestClient(app_core.app) as client:
    health=client.get('/api/health').json()
    assert health['profile']=='core' and health['models_ready'] is False
    assert health['capabilities']['file_import'] is True
    assert health['capabilities']['sources']==['local_file','podcast']
    for path in ('/api/login','/api/batches','/api/discovery/search','/api/tasks'):
        assert client.post(path,json={'share_text':'https://example.com'}).status_code in (404,405)
    assert client.post('/api/settings',headers={'Origin':'https://evil.example'},json={}).status_code==403
    assert client.get('/studio/').status_code==200
    assert client.get('/logo.svg').status_code==200
    assert client.get('/api/settings').json()['key_configured'] is False
    assert store.get(record['id'])==before
    task={'id':'bbbbbbbbbbbbbbbb','source':{'kind':'local_file'},'title':'测试','status':'completed','created_at':2,
          'result':{'text':'保留原话。','segments':[{'text':'保留原话。','start':0,'end':2}]}}
    store.save(task)
    doc=client.get('/api/studio/documents/'+task['id']).json()
    assert doc['revision']==1 and len(doc['sources'])==1
    content={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'编辑稿。'}]}]}
    changed=client.put('/api/studio/documents/'+task['id'],json={'revision':1,'content':content})
    assert changed.status_code==200 and changed.json()['revision']==2
    assert store.get(task['id'])['result']['text']=='保留原话。'
    assert client.get('/api/studio/documents/'+task['id']+'/export/txt').status_code==200
    assert client.get('/api/library/items').status_code==200
assert not any(n in sys.modules for n in ('pipeline','batches','session','extractor','discovery','app'))
print(json.dumps({'boot':'ok','unknown_task':'unchanged','draft_versions':2,'private_imports':0}))
'''
            result = subprocess.run([sys.executable, '-B', '-c', script], cwd=root, env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=50)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertIn('"private_imports": 0', result.stdout)


if __name__ == '__main__':
    unittest.main()
