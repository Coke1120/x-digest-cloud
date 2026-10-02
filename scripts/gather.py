"""Gather real twitter-cli JSON to private disk; emit only bounded summaries."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from x_env import SetupError, child_environment, cli, live_status

QUERIES = [
    '(OpenAI OR Anthropic OR DeepSeek OR Qwen OR Gemini OR GLM OR Kimi OR MiniMax) (release OR released OR pricing OR benchmark OR 发布 OR 开源)',
    '(LLM OR "AI model" OR "AI research") (paper OR benchmark OR evaluation OR reproducible OR research OR 论文 OR 评测)',
    '(OpenClaw OR "Claude Code" OR Codex OR "DeepSeek Harness") (release OR update OR plugin OR skill OR bug OR fix OR 发布 OR 更新 OR 修复)',
    '(MCP OR Rolldown OR Vite OR Unity OR Copilot) (release OR RFC OR changelog OR fix OR SDK OR 发布 OR 修复)',
    '(vLLM OR SGLang OR MLX OR llama.cpp OR CUDA OR GPU) (benchmark OR latency OR throughput OR VRAM OR quantization OR 量化 OR 性能)',
    '("open source" OR "open-source" OR 开源) (agent OR AI OR LLM) (released OR launch OR GitHub OR demo OR 发布)',
    '("AI safety" OR alignment OR "AI regulation") (research OR standard OR evaluation OR policy OR 报告 OR 监管)',
    '(OpenAI OR Anthropic OR Nvidia OR AMD OR Stripe OR stablecoin) (funding OR IPO OR valuation OR earnings OR pricing OR 融资 OR 上市 OR 财报)',
]
WATCHLIST = ['OpenAI', 'AnthropicAI', 'deepseek_ai', 'openclaw', 'sama', 'steipete', 'emollick', 'dotey', 'simonw', 'lidangzzz', 'levelsio', 'unsafemut', 'sydneyrunkle', 'unitygames']


def plan(since, n, user_n):
    jobs = [('search-%s-%02d.json' % (order.lower(), i), ['search', query, '-t', order, '--max', str(n), '--exclude', 'retweets', '--since', since]) for i, query in enumerate(QUERIES) for order in ('Top', 'Latest')]
    jobs += [('feed-%s.json' % tab, ['feed', '-t', tab, '--max', str(n)]) for tab in ('following', 'for-you')]
    jobs += [('user-%s.json' % handle, ['user-posts', handle, '--max', str(user_n)]) for handle in WATCHLIST]
    return jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', required=True, type=Path)
    parser.add_argument('--since', default=(datetime.now(timezone.utc) - timedelta(hours=24)).strftime('%Y-%m-%d'))
    parser.add_argument('--n', type=int, default=12)
    parser.add_argument('--user-n', type=int, default=4)
    parser.add_argument('--plan', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.n <= 50 or not 1 <= args.user_n <= 50:
        parser.error('Counts must be between 1 and 50')
    try:
        datetime.strptime(args.since, '%Y-%m-%d')
    except ValueError:
        parser.error('Use --since YYYY-MM-DD')
    jobs = plan(args.since, args.n, args.user_n)
    if args.plan:
        print(json.dumps({'calls': len(jobs), 'since': args.since, 'jobs': jobs}, ensure_ascii=False))
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
    (output / '_gather_summary.json').write_text(json.dumps(footer, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in footer.items() if key != 'calls_detail'}))
    return 0 if footer['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
