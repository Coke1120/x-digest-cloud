---
name: X digest editorial
description: >-
  use this when producing Leo’s finalized-v1 standalone Traditional Chinese
  X/Twitter 24h digest — Hong Kong time label, varied punchlines (意味著 optional),
  disk-only gather, prefilter, honest IDs; reader-facing digest has no meta
  notes; no cron unless asked
---
# X/Twitter 24h Traditional Chinese digest (editorial)

**Status: finalized v1** (2026-09-13; punchline + timezone label refined). Standalone, token-thrifty. Do **not** fetch/diff/cite third-party digests during a normal run. Do **not** enable cron/publish unless the user explicitly asks.

Use when producing a plain-text Traditional Chinese 24h X/Twitter digest via Agent-Reach / twitter-cli.

## Hard rules
- Traditional Chinese
- **Never invent tweet IDs** — every ID must appear in twitter-cli JSON under `/tmp/x-digest-raw-*/`
- Auth: use this package's `scripts/x_env.py` adapter with explicitly configured Agent-Reach credentials; never print secrets. The old `load-twitter-env.py` helper is not a prerequisite.
- Use both `twitter search -t Top` and `-t Latest`; if search 404s, fix ClientTransaction (`https://x.com/home` + cookies) / twitter-cli ≥0.8.6, or fall back to feed + user-posts
- **Token thrift (strict):** disk-only gather → prefilter `candidates.jsonl` → LLM reads candidates only
- **Reader-facing copy only:** the digest file must not contain meta notes (no「句式示範」、pipeline 說明、內部編輯備註). Put process notes in `*-NOTES.md` only.

## Bullet style (punchline)
Shape: `Name（@handle）事實摘要；收束句。（tweetId）`

Closing after `；` is a short takeaway — **do not force `意味著…` on every line.** Vary endings (趨勢／保留／定調). Use `意味著…` only when a structural implication fits naturally (minority).

Unverified claims must stay labeled (傳聞／個人推測／未經證實).

## Timestamp
Use **`最後更新：香港時間 YYYY-MM-DD HH:MM`** (Asia/Hong_Kong). Do **not** write 台北時間.

## Categories
**Required twelve:** AI 模型與研究｜OpenClaw／Agent 生態｜開發者工具｜產業｜財經｜本地 AI／部署與推理｜AI 安全／私隱與合規｜算力／晶片與硬件｜香港與區域要聞｜國際重大新聞｜科學／醫療與健康｜環境／能源與公共安全

Keep all twelve headings, even when a category has zero supported events. The owner's updated target (2026-10-08) is at least ten substantive independent events in every category, normally 10–20 per category (120–240 overall), with an absolute maximum of 300 source bullets. This supersedes the earlier no-per-category-target guidance. Review the complete eligible candidate pool for each category before declaring a shortfall; a small initial shortlist is not a reason to stop. Publish only actual supported events: the target never relaxes the exact 24-hour window, evidence quality, event deduplication or normal two-per-author rule. Record all twelve candidate/rejection/publication counts and any below-ten gap privately; never pad or split events.

Each event belongs once in its most relevant category. Hardware products/specifications go in 算力／晶片與硬件; local inference implementations/measurements in 本地 AI／部署與推理; financing and material economic data in 財經; concrete AI/privacy/security/legal developments in AI 安全／私隱與合規. Keep 產業 for business adoption, partnerships, capacity and operational developments.

General news needs a concrete material development with broad public impact: policy/court changes, elections/diplomacy/conflicts, consequential local services, published scientific results, health alerts, disasters, energy supply and public safety. Prefer attributable official statements and media with original reporting; distinguish an authority's own announcement from independent verification. Exclude routine chatter, jokes, speculative health cures, promotional trading calls, unrelated celebrity/sports stories and outrage without new facts. Regional public affairs belong in 香港與區域要聞; disaster/public-safety or scientific stories belong in the dedicated topic even when local. Finance now includes central banks, inflation, jobs, GDP, property, earnings and material deals, beyond IT. General-news discovery remains evidence-limited and does not authorize new feeds, account promotion or publication outside the genuine snapshot.

## Gather / prefilter
```bash
python3 <skill-dir>/scripts/gather.py --out-dir /tmp/x-digest-raw-YYYY-MM-DD-HHMM-vN --n 50 --user-n 12
python3 <skill-dir>/scripts/prefilter.py /tmp/x-digest-raw-YYYY-MM-DD-HHMM-vN -o <private-work-dir>/candidates.jsonl --hours 26 --limit 450
```

## Editorial dedupe
- Count each event once in its most relevant category; combine materially relevant follow-ups into its one source bullet. Publish supported actual counts, at most 300 source bullets overall.
- Substance bar: concrete claim (number, release, stance, verifiable quote)

## Output
```
## 📋 X 動態摘要（過去 24 小時）
最後更新：香港時間 YYYY-MM-DD HH:MM
### … categories …
- Name（@handle）…；收束句。（tweetId）
### 📊 統計
### 📝 總結
```
Files: `<private-output-dir>/x-digest-YYYY-MM-DD-vN.md` + a separate `…-NOTES.md` (process/funnel only in NOTES). Preserve same-day versions. Keep this editorial reference aligned when rules change.

## Discovery and hourly changes (2026-10-02)
- Use Top and Latest across the twelve concrete topic queries. Anchor accounts provide continuity, not an exclusive source list. Include maintainers, researchers and hands-on users found outside the anchors.
- Rank concrete releases, fixes, reproducible measurements and technical detail above engagement. Popularity is bounded and receives no watchlist boost. Candidate selection reserves opportunities across topics and outside the anchors; this is not a required publication quota.
- Normally at most two bullets per author. Distinct major first-party announcements may justify an exception, documented privately. Keep one lead and at most two substantive follow-ups per event, even when different accounts discuss it.
- Compare every claim with full text and label third-party reporting, rumours and personal judgments. A release keyword, link or derived quality signal is not proof. Remove unsupported product promises, contextless reactions, copied promotions and repetitive commentary.
- Read the previous edition through the verified Site helper before drafting. Use `[本次新增] ` before Name only for a story absent from that edition; use `[有進展] ` only for a materially changed fact about an existing story. A different source ID with the same facts is not new. Leave repeated facts unmarked in the rolling-24h overview. Do not compare with other publishers' digests.
- The optional prefix keeps the source shape: `- [本次新增] Name（@handle）事實摘要；收束句。（tweetId）`. Keep one genuine ID per bullet and the original Hong Kong label. Markers are reader content; funnel counts, source limitations and any author-cap exceptions remain private notes.
- Use the twelve required categories and actual supported counts above; retain the exact 24-hour window and maximum 300. No source, category, author or change-marker quota may admit weak material.

## Source pools and evidence review (2026-10-03)
- The user separately authorized weekly DeepSRT selection-pattern analysis. Follow `editorial/selection-pattern-review.md` and its private JSON state when due. This is an explicit exception to the normal-run third-party-digest ban, limited to editorial pattern analysis; our own genuine collector snapshot (X plus the two owner-approved official feeds) remains the sole publication evidence.
- Use `scripts/source_pool.json` as the reviewed source registry: four core plus ten rotating reviewed accounts. Select one language-rotating query per each of twelve lanes, each in Top and Latest, plus two feeds: at most forty X calls. Search English, Traditional/Simplified Chinese and Japanese across runs. Each new general-news lane receives a discovery search every run; discovery results remain unreviewed and source roles remain hints.
- Treat account role, primary-profile links, first-person wording, claim-kind and measurement-context fields as selection hints. They never authenticate a claim or establish first-party authorship. Read the entire source and identify the actual relationship of the author to the event.
- Classify each selected item privately as first-party release, first-hand measurement/experience, third-party report, or attributed opinion. Favor the first two when equally substantive; do not impose a role quota. Exclude pure reactions, jokes, generic praise/complaints, promotional trading calls and commentary that adds no concrete information.
- For speed/cost/quality comparisons, preserve the stated model, precision, hardware, context/batch, task and measurement method whenever available. State that missing conditions limit comparability. Do not generalize a single demo or personal run into a universal capability, a market trend or a proven performance advantage.
- Keep finance about verifiable financial developments (earnings, funding, acquisitions, infrastructure spending, payments or material macro data); unrelated politics, sports and celebrity scandals cannot fill this category.
- Record counts per category for available candidates, excluded window, weak evidence, duplicate events, promotional/opinion-only and unrelated items, plus published evidence-kind counts, in private notes. Mechanical `coverage.selection_diagnostics` is not semantic review; explain the actual coverage gap after reviewing evidence.
- Read private `data/source_health.json` only for source maintenance when needed. Candidate suggestions remain unreviewed. The initial official/maintainer seed pool uses matching primary profile/project links; this verifies identity only, not the quality of an individual post. Before promoting an unreviewed discovery author to the registry, verify identity/project affiliation through a primary project/profile link and review at least three substantive, distinct source posts on at least two dates. Retain genuine source IDs in its verification record; use no follower/engagement threshold and no other digest as evidence.
- Review the source registry monthly using a week's collection and semantic-rejection notes. Pause inactive, copied, promotional or repeatedly misleading sources, and retain infrequent maintainers whose releases remain useful. Do not automatically promote an author from keyword scores or remove them simply for low volume. Registry entries not reviewed within sixty days are excluded until renewed.

## Latest successful source policy (2026-10-03)
Use the latest successful snapshot pinned to current main without a fixed maximum collection age. Keep invalid/future times, failed latest collection, source-regression, duplicate-run and current rolling-24h post checks. Include the true `資料收集截至：香港時間 YYYY-MM-DD HH:MM` cutoff separately from the current publication label; do not claim observations after the collection cutoff. If no supported current-window items remain, preserve the last edition. Keep enabled tasks active on delayed/missing collector starts and transient errors, retrying on the saved schedule.


## Owner-added official release feeds (2026-10-06)

Collect the two exact public RSS feeds alongside each successful X run:
- https://x.ai/changelog/bot/rss.xml (xAI Grok Bot)
- https://openai.com/products/release-notes/rss.xml (OpenAI product releases; the owner supplied this RSS in place of scraping the Traditional Chinese page).

Run `scripts/official_sources.py` before building the snapshot. It uses no credentials, refuses redirects, limits response size and entry count, strips executable HTML, retains publisher, original GUID, canonical official URL, full text and original publication time. Store these separately as `official_records`, `official_coverage` and `official_collected_at` inside the same schema-version-1 snapshot. Never manufacture a tweet ID or author handle for RSS. Failed feeds expose safe coverage codes and contribute no records; ordinary verified X collection may continue. A successful empty current-window feed is not a failure. RSS is additional to the existing forty X calls and does not change credentials, schedules or the account pool.

For each editorial run inspect both compact official candidates and full official records pinned to the same main commit. Official records are publication evidence only after full semantic review; they do not require a matching X post. This owner-approved addition supersedes statements limiting publication evidence to X alone. Apply the same exact rolling 24-hour window, real collection cutoff, source-regression, duplicate-run, category, maximum-300 and novelty rules. Use original `published_at` only; a changed translation, RSS GUID, wording, update timestamp or recollection is not a new event. Missing or date-only publication times are excluded. Official releases and X accounts covering the same event count once, preferably using the first-party official record. Treat official marketing or capability claims as attributed claims, not independent measurements. Normally at most two substantive events per publisher; privately document distinct major first-party exceptions.

Official source bullets use `- [本次新增] OpenAI（官方）事實摘要；收束句。（official:openai:<24-hex-id>） [來源](<exact-record-url>)`, with `xAI` and `official:xai:` for the other feed. The marker is optional or `[有進展]` under the existing semantic novelty rules. Cite the actual collector-provided nonnumeric ID and exact URL; never use a fake handle or numeric tweet ID. The updated Site validates publisher, feed URL, GUID-derived ID, coverage, publication time, window, URL and uniqueness. Include official and X evidence-kind/category/exclusion counts in private notes. The public JSON reports official IDs and source URLs while omitting GUIDs, private notes and full feed evidence. Routine updates still use protected content writes without rebuilding Site code.

