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
**Default five:** AI 模型與研究｜OpenClaw／Agent 生態｜開發者工具｜產業｜財經  
**Split** if safety/governance alone would exceed ~20.  
**Optional day-only:** 開源／中國模型｜具身／機器人｜加密／Web3｜地緣與社會｜資安與 AI 治理（when that cluster dominates）

## Gather / prefilter
```bash
python3 <skill-dir>/scripts/gather.py --out-dir /tmp/x-digest-raw-YYYY-MM-DD-HHMM-vN --n 12 --user-n 4
python3 <skill-dir>/scripts/prefilter.py /tmp/x-digest-raw-YYYY-MM-DD-HHMM-vN -o <private-work-dir>/candidates.jsonl --hours 26 --limit 150
```

## Editorial dedupe
- **1 lead + ≤2 follow-ups** per story; target **10–20 substantive bullets per default category**, 50–100 total when supported; no more than 100 source bullets overall
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
- Aim for 10–20 substantive source bullets per default category, 50–100 total only when supported; cap the complete edition at 100. This supersedes the older 45–55 total target. If fewer than ten independent supported items exist in a category after semantic review, use its actual count and document the coverage gap in private notes. Keep all five default headings and count each event in its most relevant category once. Do not move unrelated items into a short category, extend the exact 24-hour window or split one story to meet its target. Never pad to satisfy a source, category, author or change-marker quota.

## Source pools and evidence review (2026-10-03)
- The user separately authorized weekly DeepSRT selection-pattern analysis. Follow `editorial/selection-pattern-review.md` and its private JSON state when due. This is an explicit exception to the normal-run third-party-digest ban, limited to editorial pattern analysis; our own genuine X snapshot remains the sole publication evidence.
- Use `scripts/source_pool.json` as the reviewed source registry. Collect four core accounts plus ten rotating accounts from the active pool, with a fixed maximum of fourteen account calls. Rotate two queries in each of six lanes (models, agents, tools, local inference, industry, finance), each in Top and Latest; search English, Traditional/Simplified Chinese and Japanese variants across runs. The six collection lanes still map to the five required reader categories; local inference belongs in AI 模型與研究 unless the event is clearly an industry or developer-tool story.
- Treat account role, primary-profile links, first-person wording, claim-kind and measurement-context fields as selection hints. They never authenticate a claim or establish first-party authorship. Read the entire source and identify the actual relationship of the author to the event.
- Classify each selected item privately as first-party release, first-hand measurement/experience, third-party report, or attributed opinion. Favor the first two when equally substantive; do not impose a role quota. Exclude pure reactions, jokes, generic praise/complaints, promotional trading calls and commentary that adds no concrete information.
- For speed/cost/quality comparisons, preserve the stated model, precision, hardware, context/batch, task and measurement method whenever available. State that missing conditions limit comparability. Do not generalize a single demo or personal run into a universal capability, a market trend or a proven performance advantage.
- Keep finance about verifiable financial developments (earnings, funding, acquisitions, infrastructure spending, payments or material macro data); unrelated politics, sports and celebrity scandals cannot fill this category.
- Record counts per category for available candidates, excluded window, weak evidence, duplicate events, promotional/opinion-only and unrelated items, plus published evidence-kind counts, in private notes. Mechanical `coverage.selection_diagnostics` is not semantic review; explain the actual coverage gap after reviewing evidence.
- Read private `data/source_health.json` only for source maintenance when needed. Candidate suggestions remain unreviewed. The initial official/maintainer seed pool uses matching primary profile/project links; this verifies identity only, not the quality of an individual post. Before promoting an unreviewed discovery author to the registry, verify identity/project affiliation through a primary project/profile link and review at least three substantive, distinct source posts on at least two dates. Retain genuine source IDs in its verification record; use no follower/engagement threshold and no other digest as evidence.
- Review the source registry monthly using a week's collection and semantic-rejection notes. Pause inactive, copied, promotional or repeatedly misleading sources, and retain infrequent maintainers whose releases remain useful. Do not automatically promote an author from keyword scores or remove them simply for low volume. Registry entries not reviewed within sixty days are excluded until renewed.

## Latest successful source policy (2026-10-03)
Use the latest successful snapshot pinned to current main without a fixed maximum collection age. Keep invalid/future times, failed latest collection, source-regression, duplicate-run and current rolling-24h post checks. Include the true `資料收集截至：香港時間 YYYY-MM-DD HH:MM` cutoff separately from the current publication label; do not claim observations after the collection cutoff. If no supported current-window items remain, preserve the last edition. Keep enabled tasks active on delayed/missing collector starts and transient errors, retrying on the saved schedule.
