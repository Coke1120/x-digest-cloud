"""Gather real twitter-cli JSON to private disk; emit only bounded summaries."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from x_env import SetupError, child_environment, cli, live_status
from source_pool import CONFIG, load_pool, rotation


def plan(since, n, user_n, pool=None, now=None, rotation_hour=None):
    selected = rotation(pool or load_pool(), now, rotation_hour)
    jobs = [('search-%s-%02d.json' % (order.lower(), i), ['search', item['query'], '-t', order, '--max', str(n), '--exclude', 'retweets', '--since', since]) for i, item in enumerate(selected['queries']) for order in ('Top', 'Latest')]
    jobs += [('feed-%s.json' % tab, ['feed', '-t', tab, '--max', str(n)]) for tab in ('following', 'for-you')]
    jobs += [('user-%s.json' % account['handle'], ['user-posts', account['handle'], '--max', str(user_n)]) for account in selected['accounts']]
    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', required=True, type=Path)
    parser.add_argument('--since', default=(datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%d'))
    parser.add_argument('--n', type=int, default=50)
    parser.add_argument('--user-n', type=int, default=12)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--source-pool', type=Path, default=CONFIG)
    parser.add_argument('--rotation-hour', type=int, help='Fixed hour for reproducible offline plans')
    args = parser.parse_args()
    if not 1 <= args.n <= 50 or not 1 <= args.user_n <= 50:
        parser.error('Counts must be between 1 and 50')
    try:
        datetime.strptime(args.since, '%Y-%m-%d')
    except ValueError:
        parser.error('Use --since YYYY-MM-DD')
    now = datetime.now(timezone.utc)
    try:
        pool = load_pool(args.source_pool)
        selected = rotation(pool, now, args.rotation_hour)
        jobs = plan(args.since, args.n, args.user_n, pool, now, args.rotation_hour)
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({'ok': False, 'code': 'invalid_source_pool'}))
        return 2
    if args.plan:
        print(json.dumps({'calls': len(jobs), 'since': args.since, 'jobs': jobs, 'selection': selected}, ensure_ascii=False))
        return 0
    # The editorial skill requires evidence beneath this exact /tmp prefix.
    output = args.out_dir.absolute()
    if output.parent != Path('/tmp') or not output.name.startswith('x-digest-raw-') or output.is_symlink():
        parser.error('Use a fresh /tmp/x-digest-raw-<run-id> directory')
    if output.exists():
        parser.error('Raw directory already exists; use a new run ID')
    try:
        env, _ = child_environment()
    except SetupError as error:
        print(json.dumps({'ok': False, 'code': str(error)}))
        return 2
    status = live_status(env)
    if not status['ok']:
        print(json.dumps({'ok': False, 'code': status['code']}))
        return 2
    os.umask(0o077)
    output.mkdir(mode=0o700)
    (output / '_collection_plan.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf-8')
    summaries = []
    blocked = False
    for filename, command in jobs:
        result = cli(command, env)
        if result.get('ok'):
            (output / filename).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        else:
            (output / filename).write_text(json.dumps({'ok': False, 'error': result.get('error'), 'data': []}), encoding='utf-8')
        data = result.get('data')
        item = {'file': filename, 'ok': result.get('ok') is True, 'n': len(data) if isinstance(data, list) else 0, 'code': result.get('error', {}).get('code')}
        summaries.append(item)
        print(json.dumps(item))
        if item['code'] in ('not_authenticated', 'rate_limited'):
            blocked = True
            break
    footer = {'done': True, 'ok': not blocked and any(item['n'] > 0 for item in summaries), 'calls': len(summaries), 'ok_calls': sum(item['ok'] for item in summaries), 'tweet_hits': sum(item['n'] for item in summaries), 'out_dir': str(output), 'since': args.since, 'calls_detail': summaries}
    footer['source_pool_revision'] = selected['revision']
    footer['rotation_hour'] = selected['rotation_hour']
    footer['sampled_accounts'] = [a['handle'] for a in selected['accounts']]
    footer['query_topics'] = [q['topic'] for q in selected['queries']]
    footer['source_review_due'] = selected['review_due']
    (output / '_gather_summary.json').write_text(json.dumps(footer, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in footer.items() if key != 'calls_detail'}))
    return 0 if footer['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

