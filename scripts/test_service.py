"""Offline origin and privacy configuration checks; no live network requests."""
from pathlib import Path
import unittest
from site_service import NoRedirect, validate_origin
from source_pool import load_pool

class ServiceTests(unittest.TestCase):
    def test_no_default_or_unlisted_destination(self):
        for allowed in (None, [], 'https://example.test', [123], ['http://example.test'],
                        ['https://example.test/path'], ['https://user@example.test'],
                        ['https://example.test?query=1'], ['https://example.test#fragment'],
                        ['https://example.test:8443']):
            with self.subTest(allowed=allowed):
                with self.assertRaises(ValueError):
                    validate_origin('https://example.test', allowed)
        with self.assertRaises(ValueError):
            validate_origin('https://other.test', ['https://example.test'])
        validate_origin('https://example.test', ['https://example.test'])

    def test_redirects_are_refused(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, None, None, 'https://other.test'))

    def test_sample_pool_is_never_a_live_source_configuration(self):
        pool = load_pool(Path(__file__).resolve().parents[1] / 'examples' / 'source_pool.json')
        self.assertTrue(all(a['status'] == 'paused' for a in pool['accounts']))
        self.assertTrue(all(a['reviewed_at'] == '2000-01-01' for a in pool['accounts']))

if __name__ == '__main__':
    unittest.main()
