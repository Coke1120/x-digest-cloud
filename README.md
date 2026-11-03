# X digest collector template

Reusable read-only X collection, bounded evidence snapshots and Traditional Chinese digest editorial guidance.

This public repository contains code, generic examples and offline tests only. It is not a live publication database and contains no configured Site, personal account pool, collection history or private editorial findings.

## Public code, private operation

Keep deployment URLs, project IDs, selected accounts, query overrides and publication preferences in your private operator configuration or ChatGPT task instructions. Never put credentials in task prompts, source, issues or logs.

Keep X credentials in GitHub Actions Secrets (`TWITTER_AUTH_TOKEN` and `TWITTER_CT0`) or an explicitly configured local Agent-Reach installation. The collector does not extract browser cookies or post, like, follow or message.

Raw results, candidate files, snapshots, source-health history and editorial notes belong in access-controlled private storage. A public repository's branches, Actions logs and artifacts are not private storage. The included workflow never commits or uploads collected evidence.

The committed `examples/source_pool.json` uses deliberately fictitious, paused accounts and expired review dates. It is a schema example, not an identity-verified source list. Copy it to ignored `private/source_pool.json`, replace every example account and verification link, review real sources, and set their review dates before collecting. The scripts fail closed when that private configuration is missing.

## Local collection

Install the pinned CLI and dependencies from `requirements.txt` in a virtual environment. With credentials explicitly configured:

```bash
python scripts/gather.py --source-pool private/source_pool.json --n 50 --user-n 12 --out-dir /tmp/x-digest-raw-RUN
python scripts/prefilter.py /tmp/x-digest-raw-RUN --source-pool private/source_pool.json -o work/candidates.jsonl --hours 26 --limit 450
python scripts/official_sources.py --output work/official-sources.json
python scripts/snapshot.py --source-repository OWNER/PRIVATE-EVIDENCE-REPO --official work/official-sources.json --raw /tmp/x-digest-raw-RUN --candidates work/candidates.jsonl --output data/latest.json
python scripts/source_health.py --source-repository OWNER/PRIVATE-EVIDENCE-REPO --source-pool private/source_pool.json --snapshot data/latest.json --output data/source_health.json
```

Use a new raw directory for every run. The 26-hour candidate buffer does not extend the exact rolling 24-hour publication window. Snapshots retain genuine full records, collection cutoff, coverage and distinct run/attempt identities; selection scores and role fields are hints, not semantic validation.

`--source-repository` must identify the actual verified evidence repository. In Actions it defaults to `GITHUB_REPOSITORY`; never copy a different repository identity to bypass a publisher's source policy.

The workflow runs credential-free tests on pull requests and relevant pushes. Manual collection requires an explicit opt-in and a private source-pool JSON supplied through the `DIGEST_SOURCE_POOL_JSON` Actions Secret. Evidence remains ephemeral until the operator implements a private, authenticated storage destination. No collection schedule or publication is enabled by this template.

## Protected Site client

`scripts/site_service.py` has no built-in personal origin. It reads one JSON line through hidden stdin in a PTY. Supply:

- `origin`: the exact HTTPS origin confirmed by fresh Site metadata.
- `allowed_origins`: a nonempty explicit list of metadata-verified origins from private operator configuration.
- `token`: a fresh service-access token, held only in memory.
- `operation`: `status`, `instructions`, `read`, `publish` or `mcp`.

The helper rejects non-origin URLs, unlisted origins and redirects, and sends the token in both authorization headers. Do not put real tokens in command arguments, files, examples, repository secrets or task prompts. Public reading does not authorize publication. Preserve the publisher's separate writer protection and audience.

Publication JSON is credential-free and requires a complete verified snapshot, pinned source commit, actual full-text semantic review, private process notes and complete reader-route readback. See `editorial/rules.md`.

## ChatGPT task setup

Store your non-secret deployment identity, source policy, preferred categories/languages, private source-pool configuration and operating procedure in the existing task's private prompt. Retain the task's timezone and explicitly chosen daily time. Fetch code pinned to a commit; obtain runtime credentials only through supported metadata or secret mechanisms.

Before enabling the task, configure private evidence storage and verify collection, authenticated publication and full readback independently. Without that storage, preserve the last edition and report `private_evidence_store_unconfigured`; do not fall back to committing raw data here. A task prompt is not an evidence store.

Optional source-pattern review state must also remain in private storage. Do not recreate it in the public repository.

## Offline tests

```bash
python -m unittest discover -s scripts -p 'test_*.py'
```

Tests use synthetic fixtures only and make no authenticated network requests.

## Privacy limitations

Removing a file in a new commit does not erase previous commits, forks, clones, Actions artifacts or caches. Historical cleanup requires a separate reviewed history-rewrite plan and, if necessary, GitHub support. Rotate any exposed credential rather than relying on deletion. This template does not claim that Git history has been purged.
