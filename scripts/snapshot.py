"""Save bounded full source records for the private hourly editorial task."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
from prefilter import _parse_ts


def collection_id(run_id, run_attempt=1):
    """Keep original run IDs; give each actual rerun its own numeric identity."""
    run_id = str(run_id)
    attempt = int(run_attempt)
    if attempt < 1 or attempt > 9999:
        raise ValueError('invalid_run_attempt')
    if attempt == 1:
        return run_id
    if not re.fullmatch(r'\d{5,15}', run_id):
        raise ValueError('invalid_github_run_id')
    return run_id + str(attempt).zfill(4)


def build(raw_dir, candidates, run_id, run_attempt=1, official=None):
    summary = json.loads((raw_dir / '_gather_summary.json').read_text())
    if summary.get('ok') is not True:
        raise ValueError('collection_not_successful')
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=26)
    # JSONL is delimited by LF; Unicode line separators can appear inside JSON strings.
    selected = [json.loads(line) for line in candidates.read_text().split('\n') if line.strip()]
    records = []
    seen = set()
    for row in selected:
        filename = row.get('source', '')
        if Path(filename).name != filename or not filename.endswith('.json'):
            raise ValueError('invalid_source_file')
        payload = json.loads((raw_dir / filename).read_text())
        originals = payload.get('data', []) if isinstance(payload, dict) else payload
        if not isinstance(originals, list):
            continue
        source = next((x for x in originals if isinstance(x, dict) and str(x.get('id') or x.get('tweetId')) == row['id']), None)
        if not source or source.get('isRetweet') or row['id'] in seen:
            continue
        author = source.get('author') or {}
        handle = (author.get('screenName') or author.get('username') or '').lstrip('@')
        text = source.get('text') or source.get('fullText') or source.get('full_text') or ''
        ts = _parse_ts(str(source.get('createdAtISO') or source.get('createdAt') or ''))
        if not handle or not text or ts is None or ts.tzinfo is None or not cutoff <= ts <= now:
            continue
        seen.add(row['id'])
        records.append({'id': row['id'], 'author': {'screenName': handle, 'name': author.get('name') or handle},
                        'text': text, 'createdAtISO': ts.astimezone(timezone.utc).isoformat(),
                        'isRetweet': False, 'source': filename,
                        'url': 'https://x.com/i/status/' + row['id'], 'candidate_text': row['text'],
                        'candidate_context': {key: row[key] for key in (
                            'category', 'selection_lane', 'selection_score', 'quality_signals', 'sources',
                            'claim_kind_hint', 'first_person_hint', 'source_role_hint',
                            'source_verification_hint', 'measurement_context_hint') if key in row}})
    if not records:
        raise ValueError('no_verifiable_candidates')
    result = {'schema_version': 1, 'run_id': collection_id(run_id, run_attempt),
              'github_run_id': str(run_id), 'github_run_attempt': int(run_attempt),
              'collected_at': now.isoformat(),
              'source_repository': 'Coke1120/x-digest-cloud', 'coverage': summary,
              'records': records[:150]}
    if official is not None:
        feeds = json.loads(official.read_text(encoding='utf-8'))
        if feeds.get('schema_version') != 1 or not isinstance(feeds.get('records'), list) or len(feeds['records']) > 80:
            raise ValueError('invalid_official_snapshot')
        fetched = _parse_ts(feeds.get('collected_at', ''))
        if fetched is None or fetched.tzinfo is None or fetched > now:
            raise ValueError('invalid_official_collection_time')
        result['official_records'] = feeds['records']
        result['official_coverage'] = feeds['coverage']
        result['official_collected_at'] = feeds['collected_at']
    diagnostics = raw_dir / '_prefilter_diagnostics.json'
    if diagnostics.exists():
        report = json.loads(diagnostics.read_text())
        if report.get('semantic_reviewed') is not False:
            raise ValueError('invalid_selection_diagnostics')
        result['coverage']['selection_diagnostics'] = report
    # GitHub contents access remains below 1 MiB; remove lowest-ranked records intact.
    while len(json.dumps(result, ensure_ascii=False).encode()) > 750_000 and result['records']:
        if result.get('official_records'):
            result['official_records'].pop()
        else:
            result['records'].pop()
    if not result['records']:
        raise ValueError('source_snapshot_too_large')
    result['record_count'] = len(result['records'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--official', type=Path)
    parser.add_argument('--raw', required=True, type=Path)
    parser.add_argument('--candidates', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = build(args.raw, args.candidates, os.environ.get('GITHUB_RUN_ID', 'manual'),
                   os.environ.get('GITHUB_RUN_ATTEMPT', '1'), args.official)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(args.output)
    print(json.dumps({'ok': True, 'records': result['record_count'], 'collected_at': result['collected_at']}))


if __name__ == '__main__':
    main()
