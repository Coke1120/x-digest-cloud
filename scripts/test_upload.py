"""Synthetic offline checks: never send requests or expose evidence in logs."""
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from upload_snapshot import endpoint_url, envelope, upload, main


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.env = {'GITHUB_RUN_ID': '123456789', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_SHA': 'a'*40, 'GITHUB_REPOSITORY': 'example/collector'}
        self.snapshot = {'schema_version': 1, 'run_id': '123456789', 'github_run_id': '123456789',
                         'github_run_attempt': 1, 'code_sha': 'a'*40, 'source_repository': 'example/collector',
                         'collected_at': datetime.now(timezone.utc).isoformat(), 'coverage': {'ok': True},
                         'records': [{'text': 'PRIVATE_EVIDENCE'}], 'record_count': 1}
        self.health = {'schema_version': 1, 'updated_at': self.snapshot['collected_at'],
                       'semantic_reviewed': False, 'runs': [{'run_id': '123456789'}]}

    def test_endpoint_is_https_exact_route_without_credentials_or_redirects(self):
        self.assertEqual(endpoint_url('https://example.test/api/private/snapshots'),
                         'https://example.test/api/private/snapshots')
        for value in (None, '', 'http://example.test/api/private/snapshots',
                      'https://example.test/api/private/snapshots?secret=x',
                      'https://example.test/api/private/snapshots#x',
                      'https://example.test:443/api/private/snapshots',
                      'https://token@example.test/api/private/snapshots',
                      'https://127.0.0.1/api/private/snapshots',
                      'https://localhost/api/private/snapshots',
                      'https://example.local/api/private/snapshots',
                      'https://example.test/api/publish'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                endpoint_url(value)

    def test_token_format_matches_server(self):
        for token in ('x'*31, 'x'*257, 'x'*32+'!', 'x'*32+' '):
            with self.assertRaises(ValueError):
                upload('https://example.test/api/private/snapshots', token, b'{}')

    def test_proof_is_bound_to_current_runner_and_full_payload(self):
        self.assertIn(b'PRIVATE_EVIDENCE', envelope(self.snapshot, self.health, self.env))
        for key, value in [('code_sha', 'b'*40), ('run_id', '987654321'), ('github_run_attempt', 2),
                           ('source_repository', 'other/repo'), ('record_count', 2),
                           ('collected_at', (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                envelope(dict(self.snapshot, **{key: value}), self.health, self.env)
        for key in self.env:
            with self.assertRaises(ValueError):
                envelope(self.snapshot, self.health, dict(self.env, **{key: ''}))
        with self.assertRaises(ValueError):
            envelope(self.snapshot, dict(self.health, semantic_reviewed=True), self.env)
        with self.assertRaises(ValueError):
            envelope(self.snapshot, dict(self.health, notes='x'*250_000), self.env)

    def test_acknowledgement_must_match_proof_and_uses_only_collector_header(self):
        data = envelope(self.snapshot, self.health, self.env)
        from unittest.mock import MagicMock
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 201
        response.headers = {'Content-Type': 'application/json'}
        response.read.return_value = json.dumps(dict(saved=True, **{
            k:self.snapshot[k] for k in ('run_id', 'code_sha', 'collected_at')})).encode()
        self.assertTrue(upload('https://example.test/api/private/snapshots', 'x'*48, data, opener)['ok'])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header('X-digest-collector-authorization'), 'Bearer '+'x'*48)
        self.assertIsNone(request.get_header('X-digest-authorization'))
        response.read.return_value = b'{"saved":true,"run_id":"other"}'
        with self.assertRaises(ValueError):
            upload('https://example.test/api/private/snapshots', 'x'*48, data, opener)

    def test_http_errors_never_print_response_body_or_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, health = Path(directory)/'snapshot.json', Path(directory)/'health.json'
            snapshot.write_text(json.dumps(self.snapshot)); health.write_text(json.dumps(self.health))
            error = urllib.error.HTTPError('https://private.example.test', 403, 'PRIVATE_EVIDENCE', {},
                                           io.BytesIO(b'PRIVATE_EVIDENCE'))
            output = io.StringIO()
            with patch.dict(os.environ, self.env), patch('sys.argv', ['uploader', '--snapshot', str(snapshot), '--source-health', str(health)]), patch('upload_snapshot.upload', side_effect=error), redirect_stdout(output):
                self.assertEqual(main(), 2)
            self.assertEqual(json.loads(output.getvalue()), {'ok': False, 'code': 'upload_http_403'})


if __name__ == '__main__':
    unittest.main()
