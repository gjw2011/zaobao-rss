from datetime import datetime, timezone
from email.utils import format_datetime
import html, os, time
import feedparser

MIRRORS = [
    "https://rsshub.app",
    "https://rsshub.gao-jiawei.com",
]
ROUTES = [
    ("中国", "/zaobao/realtime/china"),
    ("国际", "/zaobao/realtime/world"),
    ("新加坡", "/zaobao/realtime/singapore"),
    ("财经", "/zaobao/realtime/zfinance"),
]

def esc(v):
    return html.escape(str(v or ""), quote=True)

def cdata(v):
    return str(v or "").replace("]]>", "]]]]><![CDATA[>")

def fetch(route):
    for base in MIRRORS:
        feed = feedparser.parse(
            base.rstrip("/") + route,
            request_headers={"User-Agent": "zaobao-rss/1.0"}
        )
        if feed.entries:
            return feed.entries
    return []

def epoch(entry):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return time.mktime(value)
    return 0

items = {}
for section, route in ROUTES:
    for entry in fetch(route):
        link = entry.get("link", "").strip()
        title = entry.get("title", "").strip()
        key = link or entry.get("id") or title
        if not key:
            continue
        candidate = (epoch(entry), section, entry)
        if key not in items or candidate[0] > items[key][0]:
            items[key] = candidate

ordered = sorted(items.values(), key=lambda x: x[0], reverse=True)[:200]
now = datetime.now(timezone.utc)

xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    "<channel>",
    "<title>联合早报 · 聚合 RSS</title>",
    "<link>https://www.zaobao.com.sg/</link>",
    "<description>联合早报：中国、国际、新加坡、财经新闻聚合</description>",
    "<language>zh-CN</language>",
    f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>",
    '<atom:link href="https://gjw2011.github.io/zaobao-rss/rss.xml" rel="self" type="application/rss+xml"/>',
]

for ts, section, entry in ordered:
    title = entry.get("title", "")
    link = entry.get("link", "")
    guid = entry.get("id") or link or title
    desc = entry.get("summary") or entry.get("description") or ""
    pub = format_datetime(datetime.fromtimestamp(ts, timezone.utc)) if ts else format_datetime(now)
    xml += [
        "<item>",
        f"<title>{esc(title)}</title>",
        f"<link>{esc(link)}</link>",
        f'<guid isPermaLink="false">{esc(guid)}</guid>',
        f"<category>{esc(section)}</category>",
        f"<pubDate>{pub}</pubDate>",
        f"<description><![CDATA[{cdata(desc)}]]></description>",
        "</item>",
    ]

xml += ["</channel>", "</rss>"]
os.makedirs("docs", exist_ok=True)
with open("docs/rss.xml", "w", encoding="utf-8") as f:
    f.write("\n".join(xml) + "\n")
print(f"Generated {len(ordered)} items")
