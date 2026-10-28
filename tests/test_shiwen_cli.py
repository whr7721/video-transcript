import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shiwen


class LinkCLI(unittest.TestCase):
    def test_platforms(self):
        for url,want in [('https://youtu.be/abc','youtube'),('https://b23.tv/abc','bilibili'),('https://v.douyin.com/abc','douyin'),('https://example.com/feed','rss')]:
            self.assertEqual(shiwen.platform(url),want)
        with self.assertRaises(ValueError):shiwen.platform('http://example.com')

    def test_export_contract(self):
        with tempfile.TemporaryDirectory() as d:
            result=shiwen.export(Path(d),{'text':'hello','segments':[{'start':1.25,'end':2.5,'text':'hello'}]},dict(cover=None,duration=3,publishedDate=None))
            self.assertEqual(result['subtitlesArray'],[dict(startTime=1.25,end=2.5,text='hello',index=0)])
            self.assertIn('00:00:01,250 --> 00:00:02,500',(Path(d)/'transcript.srt').read_text())

    def test_untimed_text_has_no_fake_srt(self):
        with tempfile.TemporaryDirectory() as d:
            r=shiwen.export(Path(d),{'text':'hello','segments':[{'text':'hello'}]}, {})
            self.assertEqual(r['subtitlesArray'],[])
            self.assertFalse((Path(d)/'transcript.srt').exists())

    def test_subtitle_fast_path_does_not_download(self):
        import yt_dlp
        class Y:
            def __init__(self,*a):pass
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def extract_info(self,*a,**k):return {'subtitles':{'en':[{'ext':'json3','url':'https://fixture'}]}}
            def urlopen(self,*a):
                import io
                return io.BytesIO(b'{"events":[{"tStartMs":0,"dDurationMs":1000,"segs":[{"utf8":"hello"}]}]}')
            def download(self,*a):raise AssertionError('subtitle path must not download')
        with patch.object(yt_dlp,'YoutubeDL',Y):
            _,r,media=shiwen.ytdlp('https://youtu.be/test',Path('.'),'en')
            self.assertEqual(r['segments'][0]['end'],1)
            self.assertIsNone(media)
