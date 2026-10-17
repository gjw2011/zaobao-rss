from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin
import html
import os
import re

import requests
from bs4 import BeautifulSoup

URL = "https://www.zaobao.com.sg/realtime"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SECTIONS = ["新加坡", "中国", "国际", "财经"]


def esc(value):
    return html.escape(str(value or ""), quote=True)


def fetch_news():
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    news = []
    seen = set()

    # 联合早报即时新闻文章链接
    for a in soup.find_all("a", href=True):
        title = " ".join(a.stripped_strings).strip()
        href = a.get("href", "").strip()

        if not title or len(title) < 6:
            continue

        # 只保留新闻文章
        if not re.search(
            r"/(?:realtime|news|finance)/",
            href
        ):
            continue

        link = urljoin("https://www.zaobao.com.sg", href)

        # 排除栏目页
        if link.rstrip("/") in [
            "https://www.zaobao.com.sg/realtime",
            "https://www.zaobao.com.sg/realtime/china",
            "https://www.zaobao.com.sg/realtime/world",
            "https://www.zaobao.com.sg/realtime/singapore",
            "https://www.zaobao.com.sg/realtime/zfinance",
        ]:
            continue

        if link in seen:
            continue

        seen.add(link)

        # 根据 URL 判断栏目
        section = "最新"

        lower = link.lower()

        if "/china/" in lower:
            section = "中国"
        elif "/world/" in lower or "/international/" in lower:
            section = "国际"
        elif "/singapore/" in lower:
            section = "新加坡"
        elif "/finance/" in lower or "/zfinance/" in lower:
            section = "财经"

        news.append({
            "title": title,
            "link": link,
            "section": section,
        })

    return news[:200]


def generate():
    items = fetch_news()

    now = datetime.now(timezone.utc)
    pubdate = format_datetime(now)

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" '
        'xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        "<title>联合早报 · 聚合 RSS</title>",
        "<link>https://www.zaobao.com.sg/</link>",
        "<description>联合早报即时新闻：新加坡、中国、国际、财经</description>",
        "<language>zh-CN</language>",
        f"<lastBuildDate>{pubdate}</lastBuildDate>",
        '<atom:link '
        'href="https://gjw2011.github.io/zaobao-rss/rss.xml" '
        'rel="self" type="application/rss+xml"/>',
    ]

    for item in items:
        title = esc(item["title"])
        link = esc(item["link"])
        section = esc(item["section"])

        xml.extend([
            "<item>",
            f"<title>{title}</title>",
            f"<link>{link}</link>",
            f'<guid isPermaLink="true">{link}</guid>',
            f"<category>{section}</category>",
            f"<pubDate>{pubdate}</pubDate>",
            "</item>",
        ])

    xml.extend([
        "</channel>",
        "</rss>"
    ])

    os.makedirs("docs", exist_ok=True)

    with open(
        "docs/rss.xml",
        "w",
        encoding="utf-8"
    ) as f:
        f.write("\n".join(xml) + "\n")

    print(f"Generated {len(items)} items")

    if not items:
        raise RuntimeError(
            "没有抓取到任何新闻，请检查联合早报页面结构。"
        )


if __name__ == "__main__":
    generate()
