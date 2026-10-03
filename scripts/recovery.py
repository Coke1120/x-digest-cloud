"""Read-only decision gate for one owner-authorized missed-slot recovery.

No network, credentials or trigger side effects. The existing editorial task
executes the returned job only through the connected GitHub job-rerun tool.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, TypeError, ValueError):
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def decide(runs, jobs, now):
    if now.tzinfo is None:
        raise ValueError('invalid_now')
    now = now.astimezone(timezone.utc)
    slot = now.replace(minute=17, second=0, microsecond=0)
    if slot > now:
        slot -= timedelta(hours=1)
    base = {'retry': False, 'expected_slot': slot.isoformat()}
    if now - slot < timedelta(minutes=15):
        return dict(base, reason='collector_slot_grace')
    relevant = [r for r in runs if r.get('path') == '.github/workflows/collect.yml'
                and r.get('head_branch') == 'main']
    if not relevant:
        return dict(base, reason='collector_history_unavailable')
    if any(r.get('status') != 'completed' for r in relevant):
        return dict(base, reason='collector_pending')
    if any(parse_time(r.get('created_at')) is None for r in relevant):
        return dict(base, reason='invalid_collector_time')
    latest = max(relevant, key=lambda r: parse_time(r['created_at']))
    if latest.get('conclusion') != 'success':
        return dict(base, reason='collector_latest_failed')
    matching = [j for j in jobs if str(j.get('run_id')) == str(latest.get('id'))
                and j.get('name') == 'collect']
    if len(matching) != 1:
        return dict(base, reason='collector_job_unverified')
    job = matching[0]
    started = parse_time(job.get('started_at'))
    completed = parse_time(job.get('completed_at'))
    if (job.get('status') != 'completed' or job.get('conclusion') != 'success'
            or started is None or completed is None or started > completed or completed > now):
        return dict(base, reason='collector_job_not_successful')
    # A rerun retains the original run.created_at. Use latest-attempt job times
    # too, or a successful recovery could be retried repeatedly in the same slot.
    if any(parse_time(r['created_at']) >= slot for r in relevant) or started >= slot:
        return dict(base, reason='collector_slot_has_execution')
    if now - completed < timedelta(hours=1):
        return dict(base, reason='collector_recovery_cooldown')
    if not isinstance(job.get('id'), int) or job['id'] <= 0:
        return dict(base, reason='collector_job_unverified')
    return dict(base, retry=True, reason='collector_schedule_missing',
                run_id=str(latest['id']), job_id=job['id'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    value = json.loads(args.input.read_text(encoding='utf-8'))
    result = decide(value['runs'], value['jobs'], datetime.now(timezone.utc))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
