"""Offline checks for preservation of evidence and private, unreviewed hints."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from snapshot import build as build_snapshot, collection_id


def build(*args, **kwargs):
    return build_snapshot(*args, source_repository='example/x-digest-cloud', **kwargs)
from recovery import decide


class SnapshotTests(unittest.TestCase):
    def test_full_evidence_survives_preview_and_diagnostics_never_grant_review(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            full = 'I tested this model.\u2028Paragraph separator:\u2029Next-line:\u0085 ' * 30 + 'Details beyond the compact preview.'
            original = {'id': '1980000000000000001', 'author': {'screenName': 'builder', 'name': 'Builder'},
                        'text': full, 'createdAtISO': datetime.now(timezone.utc).isoformat(), 'isRetweet': False}
            (raw/'search-top-00.json').write_text(json.dumps({'data': [original]}))
            (raw/'_gather_summary.json').write_text(json.dumps({'ok': True}))
            (raw/'_prefilter_diagnostics.json').write_text(json.dumps({'semantic_reviewed': False}))
            candidate = {'id': original['id'], 'text': full[:280], 'source': 'search-top-00.json',
                         'category': 'AI 模型與研究', 'claim_kind_hint': 'measurement_claim',
                         'source_role_hint': 'practitioner', 'measurement_context_hint': ['hardware']}
            path = raw/'candidates.jsonl'
            path.write_text(json.dumps(candidate)+'\n')
            result = build(raw, path, 'offline-test')
            self.assertEqual(result['records'][0]['text'], full)
            self.assertEqual(result['records'][0]['candidate_text'], full[:280])
            self.assertEqual(result['records'][0]['candidate_context']['measurement_context_hint'], ['hardware'])
            self.assertFalse(result['coverage']['selection_diagnostics']['semantic_reviewed'])
            retried = build(raw, path, '37103577428', 2)
            self.assertEqual(retried['run_id'], '371035774280002')
            self.assertEqual(retried['github_run_id'], '37103577428')
            self.assertEqual(retried['github_run_attempt'], 2)
            self.assertEqual(retried['records'], result['records'])
            (raw/'_prefilter_diagnostics.json').write_text(json.dumps({'semantic_reviewed': True}))
            with self.assertRaisesRegex(ValueError, 'invalid_selection_diagnostics'):
                build(raw, path, 'offline-test')

    def test_repository_identity_is_explicit_and_rejected_when_missing(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'invalid_source_repository'):
                build_snapshot(Path('.'), Path('absent.jsonl'), 'offline-test')
        for invalid in ('', 'not-a-repository', '../repo', 'owner/repo/extra'):
            with patch.dict('os.environ', {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'invalid_source_repository'):
                    build_snapshot(Path('.'), Path('absent.jsonl'), 'offline-test', source_repository=invalid)

    def test_rerun_identity_is_distinct_stable_and_numeric(self):
        original = '37103577428'
        self.assertEqual(collection_id(original, 1), original)
        self.assertEqual(collection_id(original, '2'), '371035774280002')
        self.assertNotEqual(collection_id(original, 2), collection_id(original, 3))
        self.assertNotEqual(collection_id(original, 2), collection_id('37103577429', 2))
        self.assertTrue(collection_id(original, 9999).isdigit())
        self.assertLessEqual(len(collection_id(original, 9999)), 20)
        for attempt in (0, -1, 10000, 'bad'):
            with self.assertRaises(ValueError):
                collection_id(original, attempt)

    def test_failed_collector_cannot_build_a_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw/'_gather_summary.json').write_text(json.dumps({'ok': False}))
            with self.assertRaisesRegex(ValueError, 'collection_not_successful'):
                build(raw, raw/'absent.jsonl', 'offline-test')


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
        self.run = {'id': 37103577428, 'head_branch': 'main',
                    'path': '.github/workflows/collect.yml', 'status': 'completed',
                    'conclusion': 'success', 'created_at': '2026-10-03T06:35:37Z'}
        self.job = {'id': 111147671779, 'run_id': 37103577428, 'name': 'collect',
                    'status': 'completed', 'conclusion': 'success',
                    'started_at': '2026-10-03T06:35:40Z',
                    'completed_at': '2026-10-03T06:36:58Z'}

    def test_missing_slot_permits_one_verified_job(self):
        result = decide([self.run], [self.job], self.now)
        self.assertTrue(result['retry'])
        self.assertEqual(result['job_id'], self.job['id'])

    def test_pending_run_blocks_recovery(self):
        queued = dict(self.run, id=37199999999, status='queued', conclusion=None)
        self.assertEqual(decide([queued, self.run], [self.job], self.now)['reason'], 'collector_pending')

    def test_slot_grace_does_not_misclassify_a_delayed_start(self):
        now = self.now.replace(hour=8, minute=21)
        self.assertEqual(decide([self.run], [self.job], now)['reason'], 'collector_slot_grace')

    def test_rerun_attempt_time_prevents_repeat_even_with_old_run_creation(self):
        job = dict(self.job, started_at='2026-10-03T08:35:40Z', completed_at='2026-10-03T08:36:58Z')
        self.assertEqual(decide([self.run], [job], self.now)['reason'], 'collector_slot_has_execution')

    def test_completion_cooldown_bounds_recovery(self):
        job = dict(self.job, started_at='2026-10-03T08:09:00Z', completed_at='2026-10-03T08:10:00Z')
        self.assertEqual(decide([self.run], [job], self.now)['reason'], 'collector_recovery_cooldown')

    def test_failed_latest_is_preserved_not_auto_retried(self):
        run = dict(self.run, conclusion='failure')
        self.assertEqual(decide([run], [self.job], self.now)['reason'], 'collector_latest_failed')

    def test_wrong_repo_lane_or_job_cannot_be_retried(self):
        self.assertFalse(decide([dict(self.run, head_branch='other')], [self.job], self.now)['retry'])
        self.assertFalse(decide([self.run], [dict(self.job, run_id=123)], self.now)['retry'])

    def test_future_completion_is_rejected(self):
        job = dict(self.job, completed_at=(self.now+timedelta(minutes=1)).isoformat())
        self.assertFalse(decide([self.run], [job], self.now)['retry'])


if __name__ == '__main__':
    unittest.main()
