"""Bounded topic/account rotation from reviewed configuration; no network writes."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

CONFIG = Path(__file__).with_name('source_pool.json')
TOPICS = ('models', 'agents', 'tools', 'local', 'security', 'hardware', 'industry', 'finance', 'hk_region', 'world', 'science_health', 'environment_safety')
ROLES = {'official', 'maintainer', 'researcher', 'practitioner', 'commentator', 'community'}


def load_pool(path=CONFIG):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if value.get('schema_version') != 1 or value.get('max_account_calls') != 14:
        raise ValueError('invalid_source_pool')
    if not 1 <= value.get('account_review_days', 0) <= 90:
        raise ValueError('invalid_source_pool')
    if set(value.get('topics', {})) != set(TOPICS):
        raise ValueError('invalid_source_pool')
    for queries in value['topics'].values():
        if len(queries) < 2 or len(queries) > 12 or len(set(queries)) != len(queries):
            raise ValueError('invalid_source_pool')
        if any(not isinstance(q, str) or not q.strip() or len(q) > 500 for q in queries):
            raise ValueError('invalid_source_pool')
    seen = set()
    if not 4 <= len(value.get('accounts', [])) <= 100:
        raise ValueError('invalid_source_pool')
    for account in value['accounts']:
        handle = account.get('handle', '')
        if not isinstance(handle, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
            raise ValueError('invalid_source_pool')
        if handle.lower() in seen or account.get('topic') not in TOPICS or account.get('role') not in ROLES:
            raise ValueError('invalid_source_pool')
        seen.add(handle.lower())
        if account.get('status') not in {'active', 'paused'} or not isinstance(account.get('core'), bool):
            raise ValueError('invalid_source_pool')
        datetime.strptime(account.get('reviewed_at', ''), '%Y-%m-%d')
        verification = account.get('verification', {})
        url = urlsplit(verification.get('url', ''))
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('invalid_source_pool')
        if verification.get('kind') not in {'primary_profile_link', 'existing_curated_source'}:
            raise ValueError('invalid_source_pool')
    if sum(a['core'] for a in value['accounts']) != 4:
        raise ValueError('invalid_source_pool')
    return value


def active_accounts(pool, now):
    out = []
    for account in pool['accounts']:
        reviewed = datetime.strptime(account['reviewed_at'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        age_days = (now.astimezone(ZoneInfo('Asia/Hong_Kong')).date() - reviewed.date()).days
        if account['status'] == 'active' and 0 <= age_days <= pool['account_review_days']:
            out.append(account)
    return out


def rotation(pool, now=None, rotation_hour=None):
    now = now or datetime.now(timezone.utc)
    hour = int(now.timestamp() // 3600) if rotation_hour is None else rotation_hour
    queries = []
    for index, topic in enumerate(TOPICS):
        options = pool['topics'][topic]
        offset = (hour + index) % len(options)
        queries.append({'topic': topic, 'query': options[offset]})
    active = active_accounts(pool, now)
    core = [a for a in active if a['core']]
    queues = {topic: [a for a in active if not a['core'] and a['topic'] == topic] for topic in TOPICS}
    interleaved = []
    while any(queues.values()):
        for topic in TOPICS:
            if queues[topic]:
                interleaved.append(queues[topic].pop(0))
    slots = pool['max_account_calls'] - len(core)
    if interleaved:
        offset = hour * slots % len(interleaved)
        rotating = [interleaved[(offset+i) % len(interleaved)] for i in range(min(slots, len(interleaved)))]
    else:
        rotating = []
    return {'revision': pool['revision'], 'rotation_hour': hour, 'queries': queries,
            'accounts': core + rotating,
            'review_due': [a['handle'] for a in pool['accounts'] if a['status'] == 'active' and a not in active]}


def account_hints(pool):
    return {a['handle'].lower(): {'source_role_hint': a['role'],
                                'source_verification_hint': a['verification']['kind']}
            for a in pool['accounts'] if a['status'] == 'active'}

