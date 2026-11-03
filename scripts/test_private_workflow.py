"""Regression checks for credential scope and safe private subprocess logs."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from types import SimpleNamespace
from collect_private import main


class PrivateWorkflowTests(unittest.TestCase):
    def test_collection_failures_keep_stderr_and_source_config_out_of_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {'RUNNER_TEMP':directory, 'GITHUB_RUN_ID':'123456789', 'GITHUB_RUN_ATTEMPT':'1',
                   'DIGEST_SOURCE_POOL_JSON':'{"private":"PRIVATE_SOURCE"}'}
            def fail(command, **kwargs):
                self.assertNotIn('DIGEST_SOURCE_POOL_JSON', kwargs['env'])
                kwargs['stdout'].write(b'PRIVATE_SOURCE PRIVATE_EVIDENCE')
                return SimpleNamespace(returncode=2)
            output = io.StringIO()
            with patch.dict(os.environ, env), patch('collect_private.load_pool'), patch('collect_private.subprocess.run', side_effect=fail) as run, redirect_stdout(output):
                self.assertEqual(main(), 2)
                self.assertEqual(run.call_count, 1)
            self.assertEqual(json.loads(output.getvalue()), {'ok': False, 'code':'collection_step_0_failed'})
            self.assertEqual((Path(directory)/'x-digest-private/step-0.log').stat().st_mode & 0o777, 0o600)

    def test_only_known_failure_codes_leave_private_logs(self):
        from collect_private import failure_code
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory)/'log'
            log.write_text('PRIVATE_TEXT\n{"code":"PRIVATE_HANDLE"}\n{"code":"not_authenticated","text":"PRIVATE_EVIDENCE"}\n')
            self.assertEqual(failure_code(log, 0), 'not_authenticated')
            log.write_text('{"code":"PRIVATE_URL"}\n')
            self.assertEqual(failure_code(log, 1), 'collection_step_1_failed')

    def test_workflow_separates_upload_and_x_secrets_and_never_exports_evidence(self):
        workflow = (Path(__file__).resolve().parents[1]/'.github/workflows/collect.yml').read_text()
        upload = workflow.split('- name: Upload to the collector-only private API')[1].split('- name: Remove')[0]
        collect = workflow.split('- name: Collect privately')[1].split('- name: Upload')[0]
        self.assertNotIn('TWITTER_', upload)
        self.assertNotIn('DIGEST_UPLOAD_TOKEN', collect)
        for unsafe in ('upload-artifact', 'git push', 'contents: write', 'pull_request_target'):
            self.assertNotIn(unsafe, workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('if: always()', workflow)


if __name__ == '__main__':
    unittest.main()
