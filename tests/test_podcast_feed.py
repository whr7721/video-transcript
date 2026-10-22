import unittest
from podcast_feed import parse, duration


class PodcastFeedTests(unittest.TestCase):
    def test_metadata_and_no_fake_transcript(self):
        data=b'<rss version="2.0"><channel><title>Show</title><item><title>Episode</title><description>notes are not transcript</description><enclosure url="https://example.org/a.mp3" type="audio/mpeg"/></item></channel></rss>'
        result=parse(data,'https://example.org/feed')
        self.assertEqual(result['episodes'][0]['transcripts'],[])
        self.assertTrue(result['episodes'][0]['importable'])

    def test_dtd_and_webpage_rejected(self):
        for data in (b'<!DOCTYPE rss><rss/>',b'<html><body>page</body></html>'):
            with self.assertRaises(ValueError):parse(data,'https://example.org/feed')

    def test_duration(self):
        self.assertEqual(duration('1:02:03'),3723)
        self.assertIsNone(duration('1:99'))
        self.assertIsNone(duration('unknown'))
