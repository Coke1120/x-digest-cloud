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


class PrivateServiceTests(unittest.TestCase):
    def test_private_read_and_state_routes_keep_origin_allowlist(self):
        import io, json
        from contextlib import redirect_stdout
        from unittest.mock import MagicMock, patch
        from site_service import main
        for operation, state_key, expected_method, expected_path in (
            ('private_snapshot', None, 'GET', '/api/private/snapshots/latest'),
            ('private_edition', None, 'GET', '/api/private/editions/x-digest-2026-01-01-v1'),
            ('private_state', 'source_health', 'GET', '/api/private/state/source_health'),
            ('save_private_state', 'selection_pattern_review', 'POST', '/api/private/state/selection_pattern_review')):
            value = {'origin':'https://example.test', 'allowed_origins':['https://example.test'],
                     'token':'synthetic', 'key':'x-digest-2026-01-01-v1', 'operation':operation, 'state_key':state_key, 'state':{'version':1}}
            opener = MagicMock()
            response = opener.open.return_value.__enter__.return_value
            response.headers = {'Content-Type':'application/json'}
            response.read.return_value = '{}'
            with patch('sys.stdin', io.StringIO(json.dumps(value))), patch('site_service.urllib.request.build_opener', return_value=opener), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://example.test'+expected_path)
            self.assertEqual(request.method, expected_method)
            self.assertEqual(request.get_header('X-digest-authorization'), 'Bearer synthetic')
            del value['allowed_origins']
            with patch('sys.stdin', io.StringIO(json.dumps(value))), redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                main()
