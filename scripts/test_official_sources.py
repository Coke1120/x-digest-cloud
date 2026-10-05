"""Official evidence dates, origin restriction and feed failure isolation."""
from datetime import datetime, timezone
import unittest
from official_sources import parse_feed, collect
NOW = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)
def rss(date='Mon, 05 Oct 2026 23:00:00 GMT', link='https://x.ai/changelog/bot#v1'):
    return ('<rss><channel><item><guid>version-1</guid><title>Release</title><link>'+link+
            '</link><pubDate>'+date+'</pubDate><description><![CDATA[<p>Feature</p><script>ignore</script>]]></description></item></channel></rss>').encode()
class Tests(unittest.TestCase):
    def test_real_identity_text_date_and_dedup(self):
        rows, counts = parse_feed(rss(), 'xai', NOW)
        self.assertEqual(rows[0]['text'], 'Feature')
        self.assertEqual(rows[0]['published_at'], '2026-10-05T23:00:00+00:00')
        self.assertEqual(rows[0]['id'], parse_feed(rss(), 'xai', NOW)[0][0]['id'])
        self.assertFalse(rows[0]['id'].isdigit())
    def test_future_old_naive_missing_and_wrong_origin(self):
        for date in ['Tue, 06 Oct 2026 01:00:00 GMT', 'Fri, 02 Oct 2026 23:00:00 GMT', '2026-10-05', 'bad']:
            self.assertFalse(parse_feed(rss(date), 'xai', NOW)[0])
        for link in ['https://evil.invalid/release','https://x.ai.evil.invalid/release','https://a@x.ai/release','http://x.ai/release']:
            self.assertFalse(parse_feed(rss(link=link), 'xai', NOW)[0])
    def test_atom_requires_published_not_updated(self):
        body=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>abc</id><title>A</title><updated>2026-10-05T23:00:00Z</updated><link href="https://openai.com/a"/><content>New</content></entry></feed>'
        self.assertFalse(parse_feed(body,'openai',NOW)[0])
        body=body.replace(b'<updated>',b'<published>').replace(b'</updated>',b'</published>')
        self.assertEqual(len(parse_feed(body,'openai',NOW)[0]),1)
    def test_no_entities_and_failure_isolation(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<!DOCTYPE rss><rss/>','xai',NOW)
        def fetch(url):
            return rss() if 'x.ai' in url else b'not xml'
        result=collect(fetch,NOW)
        self.assertEqual(len(result['records']),1)
        self.assertTrue(result['coverage'][0]['ok'])
        self.assertFalse(result['coverage'][1]['ok'])
if __name__=='__main__':
    unittest.main()
