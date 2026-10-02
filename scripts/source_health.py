"""Keep bounded private discovery history; never promote accounts automatically."""
import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path
import re
from prefilter import CATEGORIES, _parse_ts
from source_pool import CONFIG, load_pool

MAX_RUNS = 168
MAX_SOURCES = 100
MAX_POSTS = 20


def build(snapshot, previous, pool):
    if (snapshot.get('schema_version') != 1 or
            snapshot.get('source_repository') != 'Coke1120/x-digest-cloud' or
            snapshot.get('coverage', {}).get('ok') is not True or not snapshot.get('records')):
        raise ValueError('invalid_health_snapshot')
    now = _parse_ts(snapshot.get('collected_at', ''))
    if now is None or now.tzinfo is None:
        raise ValueError('invalid_health_timestamp')
    cutoff = now - timedelta(days=7)
    configured = {a['handle'].lower(): a for a in pool['accounts']}
    sources = {}
    for old in previous.get('sources', [])[:MAX_SOURCES]:
        handle = old.get('handle', '')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
            continue
        posts = []
        for post in old.get('posts', [])[:MAX_POSTS]:
            last_seen = _parse_ts(post.get('last_seen', ''))
            if str(post.get('id', '')).isdigit() and last_seen and last_seen.tzinfo and cutoff <= last_seen <= now:
                posts.append(post)
        if posts:
            sources[handle.lower()] = {'handle': handle, 'posts': posts}
    for record in snapshot['records'][:150]:
        handle = record.get('author', {}).get('screenName', '')
        source_id = str(record.get('id', ''))
        created = _parse_ts(record.get('createdAtISO', ''))
        if (not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle) or not source_id.isdigit() or
                not record.get('text') or record.get('isRetweet') or created is None or
                created.tzinfo is None or not now-timedelta(hours=26) <= created <= now):
            raise ValueError('invalid_health_source_record')
        item = sources.setdefault(handle.lower(), {'handle': handle, 'posts': []})
        old = next((p for p in item['posts'] if p['id'] == source_id), None)
        if old:
            old['last_seen'] = now.isoformat()
        else:
            context = record.get('candidate_context', {})
            category = context.get('category')
            item['posts'].append({'id': source_id, 'created_at': created.isoformat(),
                                  'last_seen': now.isoformat(),
                                  'category_hint': category if category in CATEGORIES else None})
        item['posts'] = sorted(item['posts'], key=lambda p: p['created_at'], reverse=True)[:MAX_POSTS]
    for key, item in sources.items():
        account = configured.get(key)
        item['status'] = 'configured' if account else 'unreviewed'
        item['distinct_posts_retained'] = len({p['id'] for p in item['posts']})
        item['distinct_post_dates_retained'] = len({p['created_at'][:10] for p in item['posts']})
        if account:
            item['role_hint'] = account['role']
            item['reviewed_at'] = account['reviewed_at']
    runs = []
    for run in previous.get('runs', [])[-MAX_RUNS:]:
        timestamp = _parse_ts(run.get('collected_at', ''))
        if timestamp and timestamp.tzinfo and cutoff <= timestamp <= now and run.get('run_id') != snapshot['run_id']:
            runs.append(run)
    coverage = snapshot['coverage']
    sampled = set(coverage.get('sampled_accounts', []))
    calls = []
    for call in coverage.get('calls_detail', [])[:40]:
        name = call.get('file', '')
        handle = name[5:-5] if name.startswith('user-') and name.endswith('.json') else ''
        if handle in sampled and handle.lower() in configured:
            calls.append({'handle': handle, 'ok': call.get('ok') is True,
                          'hits': max(0, min(50, int(call.get('n', 0))))})
    counts = Counter(r.get('candidate_context', {}).get('category') for r in snapshot['records'])
    runs.append({'run_id': str(snapshot['run_id']), 'collected_at': now.isoformat(),
                 'selected_records': len(snapshot['records']),
                 'category_hints': {k: counts[k] for k in CATEGORIES}, 'account_calls': calls})
    ordered = sorted(sources.values(), key=lambda x: (
        x['status'] != 'configured', -x['distinct_posts_retained'], x['handle'].lower()))[:MAX_SOURCES]
    result = {'schema_version': 1, 'updated_at': now.isoformat(), 'window_days': 7,
              'source_pool_revision': pool['revision'], 'semantic_reviewed': False,
              'notes': 'Candidate history is a mechanical hint. Identity and usefulness require manual review; no automatic promotion.',
              'runs': runs[-MAX_RUNS:], 'sources': ordered}
    # Keep GitHub content access below 1 MiB even for very active source pools.
    while len(json.dumps(result, ensure_ascii=False, indent=2).encode()) > 750_000 and len(result['runs']) > 1:
        result['runs'].pop(0)
    while len(json.dumps(result, ensure_ascii=False, indent=2).encode()) > 750_000 and result['sources']:
        result['sources'].pop()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-pool', type=Path, default=CONFIG)
    args = parser.parse_args()
    previous = json.loads(args.output.read_text()) if args.output.exists() else {}
    result = build(json.loads(args.snapshot.read_text()), previous, load_pool(args.source_pool))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    print(json.dumps({'ok': True, 'retained_sources': len(result['sources']), 'semantic_reviewed': False}))


if __name__ == '__main__':
    main()
