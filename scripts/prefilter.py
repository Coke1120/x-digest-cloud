#!/usr/bin/env python3
"""Collapse twitter-cli JSON dumps into a compact candidate list for LLM curation."""
from __future__ import annotations

import argparse
import json
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
        if row.get("isRetweet") and not text:
            continue
        out.append(
            {
                "id": tid,
                "handle": author.get("screenName") or author.get("username") or "",
                "name": author.get("name") or "",
                "text": text[:280],
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
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%a %b %d %H:%M:%S %z %Y",
    ):
        try:
            return datetime.strptime(s.replace("Z", "+0000"), fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=26.0)
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument(
        "--watchlist",
        default="OpenAI,AnthropicAI,sama,emollick,simonw,steipete,openclaw,code,levelsio,dotey,lidangzzz,deepseek_ai,GoogleDeepMind",
    )
    args = ap.parse_args()

    watch = {h.strip().lstrip("@").lower() for h in args.watchlist.split(",") if h.strip()}
    by_id: dict[str, dict[str, Any]] = {}
    for path in sorted(args.raw_dir.glob("*.json")):
        for row in _load_tweets(path):
            prev = by_id.get(row["id"])
            if not prev or (row["views"], row["likes"]) > (prev["views"], prev["likes"]):
                by_id[row["id"]] = row

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=args.hours)
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in by_id.values():
        if row.get("isRetweet"):
            continue
        ts = _parse_ts(str(row.get("createdAt") or ""))
        if ts is None or ts.tzinfo is None:
            continue
        if ts < cutoff or ts > now:
            continue
        handle = (row.get("handle") or "").lower()
        score = (
            float(row.get("views") or 0) * 0.001
            + float(row.get("likes") or 0) * 2.0
            + float(row.get("retweets") or 0) * 3.0
        )
        if handle in watch:
            score *= 1.35
        # light substance: has digits or URL-ish or length
        text = row.get("text") or ""
        if re.search(r"\d", text):
            score *= 1.1
        if len(text) < 40:
            score *= 0.7
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [row for _, row in scored[: args.limit]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in top:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta = {
        "unique_ids": len(by_id),
        "after_window_non_rt": len(scored),
        "candidates": len(top),
        "hours": args.hours,
        "output": str(args.output),
    }
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
