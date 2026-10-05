"""Bounded public official release feeds; never receives X or Site credentials."""
import argparse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = {
    'xai': {'publisher': 'xAI', 'url': 'https://x.ai/changelog/bot/rss.xml',
            'hosts': {'x.ai', 'docs.x.ai', 'grok.com'}},
    'openai': {'publisher': 'OpenAI', 'url': 'https://openai.com/products/release-notes/rss.xml',
               'hosts': {'openai.com', 'help.openai.com', 'developers.openai.com', 'learn.chatgpt.com'}},
}
MAX_BYTES = 2_000_000
MAX_ITEMS = 40

def official_url(value, key):
    try:
        p = urllib.parse.urlsplit(value)
        return (p.scheme == 'https' and p.hostname in FEEDS[key]['hosts']
                and p.port in (None, 443) and not p.username and not p.password)
    except (ValueError, KeyError, TypeError):
        return False

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('p', 'li', 'br', 'div', 'h1', 'h2', 'h3'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        if tag in ('p', 'li', 'div'):
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def plain(value):
    p = Text()
    p.feed(value)
    return '\n'.join(' '.join(line.split()) for line in ''.join(p.parts).splitlines() if line.strip())

def timestamp(value):
    try:
        t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        try:
            t = parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError):
            return None
    return t.astimezone(timezone.utc) if t.tzinfo else None

def field(item, names):
    for name in names:
        for child in item:
            if child.tag.split('}')[-1] == name and child.text:
                return child.text.strip()
    return ''

def parse_feed(body, key, now):
    if len(body) > MAX_BYTES:
        raise ValueError('official_feed_too_large')
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('official_feed_unsafe_xml')
    root = ET.fromstring(body)
    kind = root.tag.split('}')[-1]
    if kind not in ('rss', 'feed', 'RDF'):
        raise ValueError('official_feed_invalid_xml')
    items = [x for x in root.iter() if x.tag.split('}')[-1] in ('item', 'entry')]
    records, seen = [], set()
    counts = {'items': len(items), 'outside_window': 0, 'invalid': 0, 'duplicate': 0, 'overflow': 0}
    for item in items[:500]:
        title = plain(field(item, ['title']))
        text = plain(field(item, ['encoded', 'content', 'description', 'summary']))
        # Published time only; a later modified/updated time is never a new release.
        published = timestamp(field(item, ['pubDate', 'published', 'date']))
        url = field(item, ['link'])
        if not url:
            url = next((c.attrib.get('href', '') for c in item
                        if c.tag.split('}')[-1] == 'link' and c.attrib.get('rel', 'alternate') == 'alternate'), '')
        guid = field(item, ['guid', 'id']) or url
        if (not title or not text or not guid or published is None
                or not official_url(url, key) or len(text) > 40_000):
            counts['invalid'] += 1
            continue
        if not now - timedelta(hours=26) <= published <= now:
            counts['outside_window'] += 1
            continue
        identity = 'official:' + key + ':' + sha256(guid.encode()).hexdigest()[:24]
        if identity in seen:
            counts['duplicate'] += 1
            continue
        seen.add(identity)
        records.append({'id': identity, 'source_kind': 'official_release',
                        'source_key': key, 'publisher': FEEDS[key]['publisher'],
                        'feed_url': FEEDS[key]['url'], 'url': url, 'guid': guid,
                        'title': title, 'text': text, 'candidate_text': (title + '\n' + text)[:600],
                        'published_at': published.isoformat(), 'date_precision': 'timestamp'})
    records.sort(key=lambda x: x['published_at'], reverse=True)
    counts['overflow'] = max(0, len(records) - MAX_ITEMS)
    return records[:MAX_ITEMS], counts

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def collect(fetch=None, now=None):
    now = now or datetime.now(timezone.utc)
    records, coverage = [], []
    def request(url):
        req = urllib.request.Request(url, headers={'User-Agent': 'X-Digest-Official-Feeds/1.0',
                                                  'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'})
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            return response.read(MAX_BYTES + 1)
    for key, config in FEEDS.items():
        try:
            rows, counts = parse_feed((fetch or request)(config['url']), key, now)
            records.extend(rows)
            coverage.append({'source_key': key, 'url': config['url'], 'ok': True, 'records': len(rows), **counts})
        except urllib.error.HTTPError as e:
            coverage.append({'source_key': key, 'url': config['url'], 'ok': False, 'error': 'official_http_' + str(e.code)})
        except (urllib.error.URLError, TimeoutError, OSError):
            coverage.append({'source_key': key, 'url': config['url'], 'ok': False, 'error': 'official_network_unavailable'})
        except (ValueError, ET.ParseError):
            coverage.append({'source_key': key, 'url': config['url'], 'ok': False, 'error': 'official_feed_invalid'})
    # Use completion time for the aggregate cutoff, never a start time before entries were fetched.
    return {'schema_version': 1, 'collected_at': datetime.now(timezone.utc).isoformat() if fetch is None else now.isoformat(),
            'coverage': coverage, 'records': records}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    print(json.dumps({'records': len(result['records']), 'coverage': result['coverage']}))

if __name__ == '__main__':
    main()
