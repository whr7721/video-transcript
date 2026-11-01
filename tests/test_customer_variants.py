import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shiwen
import store


class CustomerPackage(unittest.TestCase):
    def test_local_file_transcription_and_repeat_cache(self):
        with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
            root=Path(tmp);audio=root/'原始音频.wav';audio.write_bytes(b'fixture audio')
            value={'text':'原话','segments':[dict(start=0,end=1,text='原话')]}
            args=argparse.Namespace(url=str(audio),episode=None,language='zh',summarize=False)
            with patch.object(store,'DATA',root/'data'),patch.object(store,'DB',root/'data/tasks.sqlite3'),patch('media_io.probe_media',return_value=1),patch('media_io.extract_audio'),patch('transcribe.local_transcribe',return_value=value) as asr:
                shiwen.add(args);shiwen.add(args);self.assertEqual(asr.call_count,1)
            self.assertEqual(audio.read_bytes(),b'fixture audio')

    def test_customer_rejects_douyin_before_network(self):
        from unittest.mock import MagicMock
        original=Path.exists
        def exists(p):return True if p.name=='customer-package.json' else original(p)
        with patch.object(Path,'exists',exists):
            with self.assertRaisesRegex(ValueError,'此版本不支持抖音链接'):
                shiwen.add(argparse.Namespace(url='https://v.douyin.com/fixture',language='auto',episode=None,summarize=False))

    def test_offline_model_copy_checks_hash_and_preserves_source(self):
        import hashlib
        from private_delivery import delivery_models as models
        with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
            root=Path(tmp);src=root/'source';src.mkdir();(src/'test.onnx').write_bytes(b'valid')
            expected={'test.onnx':(5,hashlib.sha256(b'valid').hexdigest())}
            with patch.object(models,'__file__',str(root/'delivery_models.py')),patch.object(models.setup_models,'FILES',expected):
                models.prepare(src,True)
                self.assertEqual((src/'test.onnx').read_bytes(),b'valid')
                self.assertEqual((root/'models/test.onnx').read_bytes(),b'valid')

    def test_corrupt_offline_model_is_not_installed(self):
        import hashlib
        from private_delivery import delivery_models as models
        with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
            root=Path(tmp);src=root/'source';src.mkdir();(src/'test.onnx').write_bytes(b'bad')
            expected={'test.onnx':(5,hashlib.sha256(b'valid').hexdigest())}
            with patch.object(models,'__file__',str(root/'delivery_models.py')),patch.object(models.setup_models,'FILES',expected):
                with self.assertRaises(RuntimeError):models.prepare(src,True)
                self.assertFalse((root/'models/test.onnx').exists())


if __name__=='__main__':unittest.main()
