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
- Prefer `twitter search -t top`; if search 404s, fix ClientTransaction (`https://x.com/home` + cookies) / twitter-cli ≥0.8.6, or fall back to feed + user-posts
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
python3 <skill-dir>/scripts/gather.py --out-dir /tmp/x-digest-raw-YYYY-MM-DD-HHMM-vN --n 12 --user-n 8
python3 <skill-dir>/scripts/prefilter.py /tmp/x-digest-raw-YYYY-MM-DD-HHMM-vN -o <private-work-dir>/candidates.jsonl --hours 26 --limit 150
```

## Editorial dedupe
- **1 lead + ≤2 follow-ups** per story; target **~45–55** bullets
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
