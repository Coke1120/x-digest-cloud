"""Read explicitly configured X credentials without exposing their values."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess


class SetupError(RuntimeError):
    pass


def child_environment():
    env = os.environ.copy()
    first, second = env.get('TWITTER_AUTH_TOKEN'), env.get('TWITTER_CT0')
    if first or second:
        if not first or not second:
            raise SetupError('incomplete_environment_credentials')
        return env, 'environment'
    directory = Path.home() / '.agent-reach'
    config = directory / 'config.yaml'
    if directory.is_symlink() or config.is_symlink():
        raise SetupError('config_symlink_rejected')
    if not config.is_file():
        raise SetupError('explicit_credentials_missing')
    if config.stat().st_size > 1024 * 1024:
        raise SetupError('config_too_large')
    if os.name != 'nt' and stat.S_IMODE(config.stat().st_mode) & 0o077:
        raise SetupError('config_permissions_must_be_600')
    try:
        import yaml
    except ImportError:
        raise SetupError('use_agent_reach_venv_python_with_pyyaml') from None
    try:
        values = yaml.safe_load(config.read_text(encoding='utf-8')) or {}
    except Exception:
        raise SetupError('invalid_agent_reach_config') from None
    if not isinstance(values, dict):
        raise SetupError('invalid_agent_reach_config')
    first, second = values.get('twitter_auth_token'), values.get('twitter_ct0')
    if not isinstance(first, str) or not isinstance(second, str) or not first or not second:
        raise SetupError('explicit_credentials_missing')
    env['TWITTER_AUTH_TOKEN'], env['TWITTER_CT0'] = first, second
    return env, 'agent_reach_config'


def cli(args, env, timeout=55):
    binary = shutil.which('twitter', path=env.get('PATH'))
    if not binary:
        return {'ok': False, 'error': {'code': 'twitter_cli_missing'}, 'data': []}
    try:
        process = subprocess.run([binary, *args, '--json'], env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': {'code': 'timeout'}, 'data': []}
    except OSError:
        return {'ok': False, 'error': {'code': 'execution_failed'}, 'data': []}
    try:
        result = json.loads(process.stdout)
    except (ValueError, TypeError):
        return {'ok': False, 'error': {'code': 'invalid_json_output'}, 'data': []}
    if isinstance(result, list) and process.returncode == 0:
        return {'ok': True, 'data': result}
    if not isinstance(result, dict) or process.returncode != 0 or result.get('ok') is False:
        code = result.get('error', {}).get('code') if isinstance(result, dict) and isinstance(result.get('error'), dict) else None
        allowed = {'not_authenticated', 'not_found', 'invalid_input', 'rate_limited', 'api_error'}
        return {'ok': False, 'error': {'code': code if code in allowed else 'cli_failed'}, 'data': []}
    if result.get('ok') is True and 'data' in result:
        return result
    return {'ok': False, 'error': {'code': 'unsupported_json_schema'}, 'data': []}


def live_status(env):
    result = cli(['status'], env, timeout=40)
    data = result.get('data')
    ok = result.get('ok') is True and isinstance(data, dict) and data.get('authenticated') is True
    return {'ok': ok, 'code': None if ok else result.get('error', {}).get('code', 'authentication_not_verified')}
