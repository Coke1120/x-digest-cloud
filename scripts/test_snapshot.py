"""Offline checks for preservation of evidence and private, unreviewed hints."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from snapshot import build


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
            (raw/'_prefilter_diagnostics.json').write_text(json.dumps({'semantic_reviewed': True}))
            with self.assertRaisesRegex(ValueError, 'invalid_selection_diagnostics'):
                build(raw, path, 'offline-test')

    def test_failed_collector_cannot_build_a_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw/'_gather_summary.json').write_text(json.dumps({'ok': False}))
            with self.assertRaisesRegex(ValueError, 'collection_not_successful'):
                build(raw, raw/'absent.jsonl', 'offline-test')


if __name__ == '__main__':
    unittest.main()
