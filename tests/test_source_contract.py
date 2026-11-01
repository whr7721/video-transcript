import json
import tempfile
import unittest
import time
from pathlib import Path

from source_contract import FileSource, TaskHandlers
from unittest.mock import patch


class DistributionTests(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
