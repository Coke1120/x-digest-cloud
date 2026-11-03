"""Run collection with all private diagnostics confined to ephemeral runner disk."""
import json
import os
from pathlib import Path
import subprocess
import sys
from source_pool import load_pool


SAFE_CODES = {'not_authenticated', 'rate_limited', 'twitter_cli_missing',
              'incomplete_environment_credentials', 'explicit_credentials_missing',
              'authentication_not_verified', 'invalid_source_pool', 'config_symlink_rejected',
              'config_too_large', 'config_permissions_must_be_600',
              'use_agent_reach_venv_python_with_pyyaml', 'invalid_agent_reach_config',
              'timeout', 'execution_failed', 'api_error', 'cli_failed'}


def failure_code(log_path, index):
    # Only known scalar codes cross the private/public boundary.
    with log_path.open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            try:
                value = json.loads(line)
                code = value.get('code')
                if isinstance(code, str) and code in SAFE_CODES:
                    return code
            except (ValueError, AttributeError):
                continue
    return 'collection_step_%d_failed' % index


def main():
    os.umask(0o077)
    try:
        root = Path(os.environ['RUNNER_TEMP']) / 'x-digest-private'
        root.mkdir(mode=0o700, exist_ok=False)
        pool = root / 'source_pool.json'
        pool.write_text(os.environ.get('DIGEST_SOURCE_POOL_JSON', ''), encoding='utf-8')
        load_pool(pool)
        run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
        if not run.isdigit() or not attempt.isdigit():
            raise ValueError('invalid_runner_identity')
        raw = Path('/tmp') / ('x-digest-raw-' + run + '-' + attempt)
        commands = [
            ['gather.py', '--source-pool', str(pool), '--n', '50', '--user-n', '12', '--out-dir', str(raw)],
            ['prefilter.py', str(raw), '--source-pool', str(pool), '-o', str(root/'candidates.jsonl'), '--hours', '26', '--limit', '450'],
            ['official_sources.py', '--output', str(root/'official-sources.json')],
            ['snapshot.py', '--official', str(root/'official-sources.json'), '--raw', str(raw), '--candidates', str(root/'candidates.jsonl'), '--output', str(root/'snapshot.json')],
            ['source_health.py', '--snapshot', str(root/'snapshot.json'), '--source-pool', str(pool), '--output', str(root/'source-health.json')],
        ]
        child_env = dict(os.environ)
        child_env.pop('DIGEST_SOURCE_POOL_JSON', None)
        for index, command in enumerate(commands):
            with (root / ('step-%d.log' % index)).open('wb') as log:
                result = subprocess.run([sys.executable, str(Path(__file__).parent/command[0]), *command[1:]],
                                        stdout=log, stderr=subprocess.STDOUT, env=child_env, timeout=900)
            if result.returncode:
                print(json.dumps({'ok': False, 'code': failure_code(root / ('step-%d.log' % index), index)}))
                return 2
        print(json.dumps({'ok': True, 'code': 'collection_ready'}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired):
        print(json.dumps({'ok': False, 'code': 'private_collection_failed'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
