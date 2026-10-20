import json
import tempfile
import unittest
from pathlib import Path

from transcribe import ROOT, clean_text, local_transcribe


class TranscriptionTests(unittest.TestCase):
    def test_unknown_token_is_visible(self):
        self.assertEqual(clean_text('<|zh|><|NEUTRAL|>这个<unk>术语'), '这个〔听辨不清〕术语')

    @unittest.skipUnless((ROOT/'data/jobs/fdd48ad811dda2cb/audio.wav').exists(), '真实样本尚未下载')
    def test_real_audio_resumes_after_interruption(self):
        runtime = ROOT/'runtime'
        runtime.mkdir(exist_ok=True)
        audio = ROOT/'data/jobs/fdd48ad811dda2cb/audio.wav'
        with tempfile.TemporaryDirectory(dir=runtime) as directory:
            cache = Path(directory).resolve()
            self.assertTrue(cache.is_relative_to(runtime.resolve()))
            def interrupt(fraction,count,text):
                if count == 3:
                    raise RuntimeError('模拟在第三段后停止')
            with self.assertRaisesRegex(RuntimeError,'模拟'):
                local_transcribe(audio,cache,interrupt)
            self.assertEqual(len(list(cache.glob('*.json'))),3)
            result = local_transcribe(audio,cache,lambda *args:None)
            reference = json.loads((audio.parent/'transcript.json').read_text(encoding='utf-8'))
            self.assertEqual(result['segments_reused'],3)
            self.assertEqual(result['text'],reference['text'])
            self.assertEqual(len(result['segments']),len(reference['segments']))


if __name__ == '__main__':
    unittest.main()
