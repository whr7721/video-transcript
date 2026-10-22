import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_models as models
import check_core
import socket


class DeploymentTests(unittest.TestCase):
    def test_pinned_download_verifies_before_success(self):
        class Response(io.BytesIO):
            status = 200
            url = 'https://release-assets.githubusercontent.com/model'
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'asset'
            data = b'correct model'
            expected = (len(data),hashlib.sha256(data).hexdigest())
            with patch.dict(models.ASSETS, {'test':expected}), patch('urllib.request.OpenerDirector.open',return_value=Response(data)):
                report = models.download('test',target,models.urllib.request.build_opener())
            self.assertEqual(report['sha256'],expected[1])
            self.assertEqual(target.read_bytes(),data)

    def test_short_corrupt_or_oversized_download_removed(self):
        class Response(io.BytesIO):
            status = 200
            url = 'https://example.org/model'
        for data in (b'a',b'bad',b'oversized'):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'partial'
                with patch.dict(models.ASSETS,{'test':(3,hashlib.sha256(b'yes').hexdigest())}), patch('urllib.request.OpenerDirector.open',return_value=Response(data)):
                    with self.assertRaises(ValueError):
                        models.download('test',target,models.urllib.request.build_opener())
                self.assertFalse(target.exists())

    def test_default_never_discovers_system_or_environment_proxy(self):
        with tempfile.TemporaryDirectory() as tmp, patch('setup_models.verify',return_value={'a':True}), patch('urllib.request.build_opener'), patch('urllib.request.ProxyHandler',wraps=models.urllib.request.ProxyHandler) as handler:
            report=models.prepare(tmp)
            handler.assert_called_once_with({})
            self.assertEqual(report['proxy_mode'],'direct')
            self.assertEqual(report['downloads'],[])

    def test_explicit_proxy_not_recorded_in_report(self):
        with tempfile.TemporaryDirectory() as tmp, patch('setup_models.verify',return_value={'a':True}):
            report=models.prepare(tmp,'http://user:password@localhost:8888')
            self.assertNotIn('password',json.dumps(report))
            self.assertEqual(report['proxy_mode'],'explicit')

    def test_archive_accepts_only_fixed_regular_members(self):
        for kind in ('missing','symlink','duplicate','correct'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); archive=root/'model.tar.bz2'; name=models.NAME+'/model.int8.onnx'
                data=b'model'; files={name:(len(data),hashlib.sha256(data).hexdigest())}
                with tarfile.open(archive,'w:bz2') as tar:
                    # An unexpected traversal name is never extracted.
                    extra=tarfile.TarInfo('../outside');extra.size=1;tar.addfile(extra,io.BytesIO(b'x'))
                    if kind!='missing':
                        member=tarfile.TarInfo(name);member.size=len(data)
                        if kind=='symlink':member.type=tarfile.SYMTYPE;member.linkname='../outside'
                        tar.addfile(member,io.BytesIO(data))
                        if kind=='duplicate':tar.addfile(member,io.BytesIO(data))
                with patch.dict(models.FILES,files,clear=True):
                    if kind=='correct':
                        models.extract_verified(archive,root/'stage')
                        self.assertEqual((root/'stage'/name).read_bytes(),data)
                    else:
                        with self.assertRaises(ValueError):models.extract_verified(archive,root/'stage')
                self.assertFalse((root/'outside').exists())

    def test_model_check_rejects_same_length_wrong_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'model';target.write_bytes(b'bad')
            self.assertFalse(models.valid(target,(3,hashlib.sha256(b'yes').hexdigest())))

    def test_preflight_missing_models_optional_or_required_without_creating_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'requirements.lock.txt').write_text('')
            (root/'frontend/dist-core').mkdir(parents=True);(root/'frontend/dist-core/index.html').touch()
            with socket.socket() as held:
                held.bind(('127.0.0.1',0));held.listen();port=held.getsockname()[1]
                with patch.object(check_core,'ROOT',root),patch.dict('os.environ',{'SHIWEN_CORE_DATA_DIR':str(root/'absent-data')}),patch.object(models,'verify',return_value={'model':False}):
                    report=check_core.check(port)
                    indexed={x['name']:x for x in report['checks']}
                    self.assertFalse(indexed['port']['ok'])
                    self.assertFalse(indexed['model:model']['required'])
                    self.assertTrue({x['name']:x for x in check_core.check(port,True)['checks']}['model:model']['required'])
                    self.assertFalse((root/'absent-data').exists())
                    (root/'models').mkdir();(root/'models/model').write_bytes(b'corrupt')
                    self.assertTrue({x['name']:x for x in check_core.check(port)['checks']}['model:model']['required'])

    def test_preflight_rejects_foreign_directory_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'requirements.lock.txt').write_text('');foreign=root/'foreign';foreign.mkdir();(foreign/'keep').write_text('unchanged')
            with patch.object(check_core,'ROOT',root),patch.dict('os.environ',{'SHIWEN_CORE_DATA_DIR':str(foreign)}),patch.object(models,'verify',return_value={}):
                report=check_core.check(0)
                self.assertFalse({x['name']:x for x in report['checks']}['data-profile']['ok'])
            self.assertEqual([x.name for x in foreign.iterdir()],['keep'])


if __name__=='__main__':unittest.main()
