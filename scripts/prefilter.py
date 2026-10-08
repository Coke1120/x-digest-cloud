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
from collections import Counter
from source_pool import CONFIG, load_pool, account_hints


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
    'AI 安全／私隱與合規': r'\b(?:ai safety|alignment|prompt injection|jailbreak|vulnerabil\w*|security advisory|privacy|copyright|licensing|regulation|governance)\b|漏洞|私隱|隐私|隱私|版權|版权|監管|监管|資安|安全承諾|安全承诺|脆弱性|プライバシー|著作権',
    '財經': r'\b(?:ipo|funding|valuation|earnings|revenue|acquisition|investment|stablecoins?|treasur(?:y|ies)|bankrupt\w*|inflation|GDP|employment|unemployment|central bank|interest rate|mortgage|property market|CPI)\b|融資|融资|上市|財報|财报|收購|收购|估值|央行|通脹|通胀|利率|樓市|楼市|就業|就业|決算|金利|雇用|買収',
    '本地 AI／部署與推理': r'\b(?:mlx|llama\.cpp|vllm|sglang|quantization|tok/s|local inference|local llm|self.hosted llm|prefill|decode|offload)\b|量化|量子化|本地.{0,8}(?:模型|推理|AI)|顯存|显存|吞吐|推論',
    '算力／晶片與硬件': r'\b(?:GPU|CPU|NVIDIA|AMD|Intel|TSMC|HBM|Blackwell|RTX|DGX|semiconductor|chip|chips|fabrication|Apple Silicon)\b|晶片|芯片|半導體|半导体|顯卡|显卡|製程|制程|半導体',
    '科學／醫療與健康': r'\b(?:clinical trial|public health|vaccine|vaccination|NASA|astronom\w*|spacecraft|medical|medicine|disease|cancer|WHO|FDA|epidemic|pandemic)\b|科學|科学|醫療|医疗|疫苗|臨床|临床|疾病|癌症|太空|航天|醫學|医学|宇宙|ワクチン|臨床試験',
    '環境／能源與公共安全': r'\b(?:severe weather|earthquake|evacuat\w*|flood\w*|wildfire|typhoon|hurricane|energy supply|power outage|climate|renewable|nuclear power|rescue|public safety)\b|颱風|台风|地震|洪水|山火|氣候|气候|能源|停電|停电|疏散|公共安全|救援|災害|灾害|警報|避難|エネルギー|気候',
    '開發者工具': r'\b(?:mcp|rolldown|vite|unity|copilot|cursor|sdk|typescript|blender|macdock|developer tools|CLI|plugin)\b|開發工具|开发工具|開発ツール',
    'OpenClaw／Agent 生態': r'\b(?:openclaw|claude code|codex|harness|agentic|agents?|opendots|dots|hermes|grok bot|skills?)\b|智能体|智能體|代理工具|エージェント',
    '產業': r'\b(?:subscription|data centers?|partnership|procurement|capacity|cloud|deployment|pricing)\b|數據中心|数据中心|雲端|雲計算|云计算|採購|采购|合作|產能|产能|企業|企业|提携|調達',
    'AI 模型與研究': r'\b(?:ai|llm|gpt\w*|openai|anthropic|deepseek|qwen|gemini|glm|kimi|minimax|astra|sol|benchmark)\b|人工智能|模型|評測|评测|モデル|ベンチマーク|AI(?=[\u4e00-\u9fff])',
    '香港與區域要聞': r'\b(?:Hong Kong|Taiwan|Macau|Macao)\b|香港|台灣|台湾|澳門|澳门',
    '國際重大新聞': r'\b(?:ceasefire|election|treaty|sanctions?|humanitarian|diplomac\w*|parliament|government|court|war|conflict|president|UN)\b|停火|選舉|选举|外交|制裁|人道|戰爭|战争|政府|法院|裁決|裁决|停戦|選挙|合意',
}
NEWS = re.compile(r'\b(?:announc\w*|confirm\w*|approv\w*|ruling|signed|agreement|results?|warning|emergency|suspended|evacuat\w*|killed|injured|passed|resign\w*|elected)\b|宣布|公布|通過|通过|裁決|裁决|批准|確認|确认|協議|协议|結果|结果|警告|疏散|緊急|紧急|停駛|死亡|受傷|發表|発表|承認|決定|警報|避難|合意', re.I)
GENERAL_CATEGORIES = {'財經', '香港與區域要聞', '國際重大新聞', '科學／醫療與健康', '環境／能源與公共安全'}

RELEASE = re.compile(r'\b(?:releas\w*|launch\w*|shipp\w*|introduc\w*|changelog|beta|open.sourc\w*|fix(?:ed|es)?|rfc)\b|发布|發布|推出|開源|开源|修复|修復|新版|リリース|修正|公開', re.I)
TECHNICAL = re.compile(r'github\.com|\b(?:github|documentation|docs|benchmark|latency|throughput|vram|quantization|sdk|rfc|install|docker|lean 4)\b|技术细节|技術細節|评测|評測|量化|復現|复现', re.I)
MEASUREMENT = re.compile(r'\d[\d.,]*\s*(?:%|gb|mb|tb|tps|tok/s|ms|seconds|倍|秒|美元|億|亿)', re.I)
PROMOTION = re.compile(r'\b(?:airdrop|giveaway|referral)\b|(?:check|查看).{0,20}(?:balance|餘額|余额)|approved posts earn|空投|返佣', re.I)
REPORT = re.compile(r'\b(?:earnings|funding round|quarterly|reported|acquisition|regulator|legislation|policy|licen[cs]e|privacy|security advisory)\b|財報|财报|融資|融资|監管|监管|決算|資金調達|規制|脆弱性', re.I)
HYPE = re.compile(r'\b(?:my bias is bullish|next 100x|guaranteed profit|buy now|price target)\b|穩賺|稳赚|必涨|必漲|無腦買|无脑买', re.I)
FIRST_PERSON = re.compile(r'\b(?:I|we)\s+(?:built|tested|measured|reproduced|implemented|released|shipped)\b|我(?:們|们)?(?:實測|实测|測試|测试|做了|開發|开发)', re.I)
CONTEXT = {
    'hardware': re.compile(r'\b(?:RTX|GPU|CPU|M[1-9]|Apple Silicon|DGX|RAM|VRAM)\b|顯卡|显卡|記憶體|内存', re.I),
    'model_or_precision': re.compile(r'\b(?:Qwen|DeepSeek|Llama|GLM|Kimi|FP\d+|BF\d+|INT\d+|Q[234568](?:_\w+)?|quantization)\b|量化|量子化', re.I),
    'method': re.compile(r'\b(?:batch|context|prompt|decode|prefill|reproducible|script|command|commit|version)\b|上下文|並發|并发|復現|复现|命令|版本', re.I),
}


def rank(row, now, hints=None):
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
    if REPORT.search(text):
        signals.append('report_or_policy_claim'); quality += 2
    if category in GENERAL_CATEGORIES and NEWS.search(text):
        signals.append('concrete_news_development'); quality += 2
    if not signals or PROMOTION.search(text) or HYPE.search(text):
        return None
    if len(text) >= 100:
        signals.append('substantive_length'); quality += 1
    if 'http' in text:
        quality += .5
    role_hints = (hints or {}).get(row['handle'].lower(), {})
    if row['handle'].lower() in OFFICIAL or role_hints.get('source_role_hint') == 'official':
        signals.append('official_account_hint')
    if quality < 1:
        return None
    age = max(0, (now - _parse_ts(row['createdAt'])).total_seconds()/3600)
    recency = max(0, 1-age/26) * 1.25
    popularity = min(1.5, math.log1p(max(0,row['likes']) + 2*max(0,row['retweets']) + max(0,row['views'])/1000)/8)
    row.update(category=category, quality_signals=signals, selection_score=round(quality+recency+popularity,4))
    row.update(role_hints)
    row['claim_kind_hint'] = ('measurement_claim' if MEASUREMENT.search(text) else
                              'release_claim' if RELEASE.search(text) else
                              'report_claim' if REPORT.search(text) or (category in GENERAL_CATEGORIES and NEWS.search(text)) else 'technical_discussion')
    row['first_person_hint'] = bool(FIRST_PERSON.search(text))
    if MEASUREMENT.search(text):
        row['measurement_context_hint'] = [name for name, pattern in CONTEXT.items() if pattern.search(text)]
    return row


def select_candidates(rows, limit, watch, now, author_limit=4, hints=None):
    ranked = []
    for row in rows:
        ts = _parse_ts(str(row.get('createdAt') or ''))
        if row.get('isRetweet') or ts is None or ts.tzinfo is None or not now-timedelta(hours=26) <= ts <= now:
            continue
        candidate = rank(dict(row), now, hints)
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
    # Reserve evidence per category before stronger high-volume topics fill capacity.
    # These are candidate opportunities, not publication quotas; never add weak rows.
    category_target = math.floor(limit / len(CATEGORIES) * .8)
    for category in CATEGORIES:
        take([r for r in unique if r['category']==category], category_target)
    take([r for r in unique if r['selection_lane']=='discovery'], max(0,math.ceil(limit*.4)-sum(r['selection_lane']=='discovery' for r in selected)))
    take([r for r in unique if r['selection_lane']=='anchor'], max(0,math.ceil(limit*.2)-sum(r['selection_lane']=='anchor' for r in selected)))
    take(unique, limit-len(selected))
    # Preserve strongest complete records if snapshot byte limits require trimming.
    selected.sort(key=lambda r: (-r['selection_score'], r['id']))
    for row in selected:
        row.pop('_full_text',None)
    return selected


def selection_report(rows, selected, now, hints):
    """Private mechanical funnel counts, never a semantic-quality verdict."""
    categories = {name: {'available': 0, 'signal_eligible': 0, 'selected': 0,
                         'weak_or_promotional': 0, 'not_selected': 0} for name in CATEGORIES}
    for row in rows:
        text = row.get('_full_text') or row['text']
        category = next((name for name, pattern in CATEGORIES.items() if re.search(pattern, text, re.I)), None)
        if category:
            categories[category]['available'] += 1
            if rank(dict(row), now, hints):
                categories[category]['signal_eligible'] += 1
            else:
                categories[category]['weak_or_promotional'] += 1
    for row in selected:
        categories[row['category']]['selected'] += 1
    for data in categories.values():
        data['not_selected'] = data['signal_eligible'] - data['selected']
    proposals = {}
    for row in selected:
        if row['handle'].lower() in hints:
            continue
        item = proposals.setdefault(row['handle'].lower(), {'handle': row['handle'], 'source_ids': [],
                                                           'category_hints': [], 'status': 'unreviewed'})
        item['source_ids'].append(row['id'])
        if row['category'] not in item['category_hints']:
            item['category_hints'].append(row['category'])
    return {'semantic_reviewed': False, 'category_funnel': categories,
            'claim_kind_hints': dict(Counter(r['claim_kind_hint'] for r in selected)),
            'source_proposals': sorted(proposals.values(), key=lambda x: (-len(x['source_ids']), x['handle']))[:20]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_dir", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=26.0)
    ap.add_argument("--limit", type=int, default=450)
    ap.add_argument(
        "--watchlist",
        default=None,
    )
    ap.add_argument('--author-limit',type=int,default=4)
    ap.add_argument('--source-pool', type=Path, default=CONFIG)
    args = ap.parse_args()
    if not 1 <= args.limit <= 450 or args.hours <= 0 or args.author_limit <= 0:
        ap.error('Use limit 1..450, positive hours and positive author-limit')

    pool = load_pool(args.source_pool)
    hints = account_hints(pool)
    watch = ({h.strip().lstrip('@').lower() for h in args.watchlist.split(',') if h.strip()}
             if args.watchlist is not None else {a['handle'].lower() for a in pool['accounts'] if a['core']})
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
    top = select_candidates(eligible,args.limit,watch,now,args.author_limit,hints)
    diagnostics = selection_report(eligible, top, now, hints)
    diagnostics.update(raw_unique_ids=len(by_id), window_eligible=len(eligible),
                       window_excluded=len(by_id)-len(eligible), source_pool_revision=pool['revision'])
    (args.raw_dir / '_prefilter_diagnostics.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding='utf-8')
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

