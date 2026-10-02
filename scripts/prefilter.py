#!/usr/bin/env python3
"""Collapse twitter-cli JSON dumps into a compact candidate list for LLM curation."""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _load_tweets(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            rows = data["data"]
        elif "id" in data:
            rows = [data]
        else:
            rows = []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # skip error payloads
        if row.get("ok") is False:
            continue
        tid = str(row.get("id") or row.get("tweetId") or "")
        if not tid.isdigit():
            continue
        author = row.get("author") or {}
        metrics = row.get("metrics") or {}
        text = (row.get("text") or row.get("fullText") or "").replace("\n", " ").strip()
        if row.get("isRetweet") or not text:
            continue
        out.append(
            {
                "id": tid,
                "handle": author.get("screenName") or author.get("username") or "",
                "name": author.get("name") or "",
                "text": text[:280],
                "_full_text": text,
                "createdAt": row.get("createdAtISO") or row.get("createdAt") or "",
                "likes": int(metrics.get("likes") or 0),
                "views": int(metrics.get("views") or 0),
                "retweets": int(metrics.get("retweets") or 0),
                "isRetweet": bool(row.get("isRetweet")),
                "source": path.name,
            }
        )
    return out


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%a %b %d %H:%M:%S %z %Y"):
        try:
            return datetime.strptime(s.replace("Z", "+0000"),fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


OFFICIAL = {'openai', 'anthropicai', 'deepseek_ai', 'openclaw', 'unitygames', 'googledeepmind'}
CATEGORIES = {
    '開發者工具': r'\b(?:mcp|rolldown|vite|unity|copilot|sdk|typescript|blender|macdock)\b|開發工具|开发工具',
    'OpenClaw／Agent 生態': r'\b(?:openclaw|claude code|codex|harness|agentic|opendots|dots|skills?)\b|智能体|智能體|代理工具',
    '財經': r'\b(?:ipo|funding|valuation|earnings|stablecoins?|treasur(?:y|ies)|bankrupt\w*|stripe|privy)\b|融资|融資|上市|財報|财报|破产|破產',
    '產業': r'\b(?:ai safety|alignment|regulation|governance|policy|subscription)\b|监管|監管|安全承诺|安全承諾',
    'AI 模型與研究': r'\b(?:ai|llm|gpt\w*|openai|anthropic|deepseek|qwen|gemini|glm|kimi|minimax|astra|sol|vllm|sglang|mlx|cuda|gpu|benchmark)\b|人工智能|模型|量化|推理|評測|评测|AI(?=[\u4e00-\u9fff])',
}
RELEASE = re.compile(r'\b(?:releas\w*|launch\w*|shipp\w*|introduc\w*|changelog|beta|open.sourc\w*|fix(?:ed|es)?|rfc)\b|发布|發布|推出|開源|开源|修复|修復|新版', re.I)
TECHNICAL = re.compile(r'github\.com|\b(?:github|documentation|docs|benchmark|latency|throughput|vram|quantization|sdk|rfc|install|docker|lean 4)\b|技术细节|技術細節|评测|評測|量化|復現|复现', re.I)
MEASUREMENT = re.compile(r'\d[\d.,]*\s*(?:%|gb|mb|tb|tps|tok/s|ms|seconds|倍|秒|美元|億|亿)', re.I)
PROMOTION = re.compile(r'\b(?:airdrop|giveaway|referral)\b|(?:check|查看).{0,20}(?:balance|餘額|余额)|approved posts earn|空投|返佣', re.I)


def rank(row, now):
    """Bounded popularity is a tie-breaker, never a substitute for evidence."""
    text = row.get('_full_text') or row['text']
    category = next((name for name, pattern in CATEGORIES.items() if re.search(pattern, text, re.I)), None)
    if not category:
        return None
    signals = []
    quality = 0.0
    for name, pattern, weight in [('release_or_fix', RELEASE, 3), ('technical_detail', TECHNICAL, 2), ('measurement', MEASUREMENT, 2)]:
        if pattern.search(text):
            signals.append(name); quality += weight
    if len(text) >= 100:
        signals.append('substantive_length'); quality += 1
    if 'http' in text:
        quality += .5
    official = row['handle'].lower() in OFFICIAL
    if official:
        signals.append('official_account'); quality += 1
    if PROMOTION.search(text):
        quality -= 4; signals.append('promotion_penalty')
    if quality < 1:
        return None
    age = max(0, (now - _parse_ts(row['createdAt'])).total_seconds()/3600)
    recency = max(0, 1-age/26) * 1.25
    popularity = min(1.5, math.log1p(max(0,row['likes']) + 2*max(0,row['retweets']) + max(0,row['views'])/1000)/8)
    row.update(category=category, quality_signals=signals, selection_score=round(quality+recency+popularity,4))
    return row


def select_candidates(rows, limit, watch, now, author_limit=4):
    ranked = []
    for row in rows:
        ts = _parse_ts(str(row.get('createdAt') or ''))
        if row.get('isRetweet') or ts is None or ts.tzinfo is None or not now-timedelta(hours=26) <= ts <= now:
            continue
        candidate = rank(dict(row), now)
        if candidate:
            candidate['selection_lane'] = 'anchor' if candidate['handle'].lower() in watch else 'discovery'
            ranked.append(candidate)
    ranked.sort(key=lambda r: (-r['selection_score'], r['id']))
    unique, signatures = [], set()
    for row in ranked:
        signature = re.sub(r'https?://\S+', '', row.get('_full_text') or row['text']).strip().casefold()
        signature = re.sub(r'\s+', ' ', signature)
        if not signature or signature in signatures:
            continue
        signatures.add(signature); unique.append(row)
    selected, used, author_counts = [], set(), {}
    def take(pool, count):
        count = min(count, limit-len(selected))
        if count <= 0:
            return
        queues = {category: [r for r in pool if r['category']==category] for category in CATEGORIES}
        while count > 0:
            progress = False
            for queue in queues.values():
                while queue:
                    row = queue.pop(0); handle = row['handle'].lower()
                    if row['id'] in used or author_counts.get(handle,0) >= author_limit:
                        continue
                    selected.append(row);used.add(row['id']);author_counts[handle]=author_counts.get(handle,0)+1
                    count -= 1;progress=True;break
                if count==0:break
            if not progress:break
    # Reserve opportunities, not publication quotas; unused capacity is reclaimed.
    take([r for r in unique if r['selection_lane']=='discovery'], math.ceil(limit*.4))
    take([r for r in unique if r['selection_lane']=='anchor'], math.ceil(limit*.2))
    take(unique, limit-len(selected))
    # Preserve strongest complete records if snapshot byte limits require trimming.
    selected.sort(key=lambda r: (-r['selection_score'], r['id']))
    for row in selected:
        row.pop('_full_text',None)
    return selected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=26.0)
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument(
        "--watchlist",
        default="OpenAI,AnthropicAI,deepseek_ai,openclaw,sama,steipete,emollick,dotey,simonw,lidangzzz,levelsio,unsafemut,sydneyrunkle,unitygames",
    )
    ap.add_argument('--author-limit',type=int,default=4)
    args = ap.parse_args()
    if not 1 <= args.limit <= 150 or args.hours <= 0 or args.author_limit <= 0:
        ap.error('Use limit 1..150, positive hours and positive author-limit')

    watch = {h.strip().lstrip("@").lower() for h in args.watchlist.split(",") if h.strip()}
    by_id: dict[str, dict[str, Any]] = {}
    for path in sorted(args.raw_dir.glob("*.json")):
        for row in _load_tweets(path):
            prev = by_id.get(row["id"])
            if not prev or (row["views"], row["likes"]) > (prev["views"], prev["likes"]):
                row['sources'] = sorted(set((prev or {}).get('sources',[]) + [path.name]))
                by_id[row["id"]] = row
            else:
                prev['sources'] = sorted(set(prev.get('sources',[]) + [path.name]))

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=args.hours)
    eligible = []
    for row in by_id.values():
        if row.get("isRetweet"):
            continue
        ts = _parse_ts(str(row.get("createdAt") or ""))
        if ts is None or ts.tzinfo is None:
            continue
        if ts < cutoff or ts > now:
            continue
        eligible.append(row)
    top = select_candidates(eligible,args.limit,watch,now,args.author_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in top:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta = {
        "unique_ids": len(by_id),
        "after_window_non_rt": len(eligible),
        "candidates": len(top),
        "hours": args.hours,
        "discovery_candidates": sum(r['selection_lane']=='discovery' for r in top),
        "distinct_authors": len({r['handle'].lower() for r in top}),
        "output": str(args.output),
    }
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
