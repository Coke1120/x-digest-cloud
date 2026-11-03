"""Upload runner evidence to a privately configured HTTPS endpoint, never stdout."""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from site_service import NoRedirect, validate_origin
from snapshot import collection_id

MAX_BYTES = 1_048_576


def endpoint_url(value):
    if not isinstance(value, str):
        raise ValueError('invalid_upload_endpoint')
    parsed = urlsplit(value)
    origin = 'https://' + parsed.netloc
    validate_origin(origin, [origin])
    if (parsed.scheme != 'https' or parsed.path != '/api/private/snapshots' or
            parsed.query or parsed.fragment or parsed.geturl() != value or
            not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+', parsed.hostname) or
            parsed.hostname.endswith(('.localhost', '.local'))):
        raise ValueError('invalid_upload_endpoint')
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError('invalid_upload_endpoint')
    return value


def envelope(snapshot, health, env):
    run_id, attempt, sha, repo = (env.get(k, '') for k in
        ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA', 'GITHUB_REPOSITORY'))
    if (not re.fullmatch(r'\d{5,15}', run_id) or not re.fullmatch(r'[1-9]\d{0,3}', attempt) or
            not re.fullmatch(r'[0-9a-f]{40}', sha) or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', repo)):
        raise ValueError('invalid_runner_identity')
    if (snapshot.get('schema_version') != 1 or snapshot.get('source_repository') != repo or
            snapshot.get('github_run_id') != run_id or snapshot.get('github_run_attempt') != int(attempt) or
            snapshot.get('run_id') != collection_id(run_id, attempt) or snapshot.get('code_sha') != sha or
            snapshot.get('coverage', {}).get('ok') is not True or
            not isinstance(snapshot.get('records'), list) or not 1 <= len(snapshot['records']) <= 450 or
            snapshot.get('record_count') != len(snapshot['records'])):
        raise ValueError('invalid_snapshot_proof')
    cutoff = datetime.fromisoformat(snapshot['collected_at'].replace('Z', '+00:00'))
    if cutoff.tzinfo is None or cutoff > datetime.now(timezone.utc):
        raise ValueError('invalid_snapshot_cutoff')
    if (health.get('schema_version') != 1 or health.get('semantic_reviewed') is not False or
            health.get('updated_at') != snapshot['collected_at'] or
            not isinstance(health.get('runs'), list) or len(health['runs']) != 1 or
            health['runs'][0].get('run_id') != snapshot['run_id']):
        raise ValueError('invalid_source_health')
    if len(json.dumps(health, ensure_ascii=False).encode()) > 250_000:
        raise ValueError('source_health_too_large')
    data = json.dumps({'snapshot': snapshot, 'source_health': health}, ensure_ascii=False).encode()
    if len(data) > MAX_BYTES:
        raise ValueError('upload_too_large')
    return data


def upload(url, token, data, opener=None):
    endpoint_url(url)
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', token):
        raise ValueError('invalid_upload_access')
    request = urllib.request.Request(url, data=data, method='POST', headers={
        'Content-Type': 'application/json', 'Accept': 'application/json',
        'X-Digest-Collector-Authorization': 'Bearer ' + token})
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    with opener.open(request, timeout=60) as response:
        if response.status not in (200, 201) or 'application/json' not in response.headers.get('Content-Type', ''):
            raise ValueError('invalid_upload_response')
        result = json.loads(response.read(4097))
        proof = json.loads(data)['snapshot']
        if (type(result.get('saved')) is not bool or
                any(result.get(k) != proof[k] for k in ('run_id', 'code_sha', 'collected_at'))):
            raise ValueError('upload_not_accepted')
    return {'ok': True, 'code': 'snapshot_uploaded'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--source-health', required=True, type=Path)
    args = parser.parse_args()
    try:
        for path in (args.snapshot, args.source_health):
            if path.stat().st_size > MAX_BYTES:
                raise ValueError('upload_too_large')
        data = envelope(json.loads(args.snapshot.read_text()), json.loads(args.source_health.read_text()), os.environ)
        result = upload(os.environ.get('DIGEST_UPLOAD_URL'), os.environ.get('DIGEST_UPLOAD_TOKEN'), data)
    except urllib.error.HTTPError as error:
        result = {'ok': False, 'code': 'upload_http_' + str(error.code)}
    except urllib.error.URLError:
        result = {'ok': False, 'code': 'upload_network_unavailable'}
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        result = {'ok': False, 'code': 'invalid_upload_request_or_response'}
    print(json.dumps(result))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
