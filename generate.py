from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin
import html
import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://www.zaobao.com.sg"
URL = BASE + "/realtime"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/18.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


def esc(v):
    return html.escape(str(v or ""), quote=True)


def cdata(v):
    return str(v or "").replace("]]>", "]]]]><![CDATA[>")


def get_summary(url):
    """读取文章公开提供的 description，不抓取付费正文。"""
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        # 优先使用网页公开的 SEO 描述
        for attrs in [
            {"property": "og:description"},
            {"name": "description"},
            {"name": "twitter:description"},
        ]:
            tag = soup.find("meta", attrs=attrs)

            if tag and tag.get("content"):
                text = " ".join(
                    tag["content"].split()
                ).strip()

                if len(text) >= 20:
                    return text

    except Exception as e:
        print("Summary error:", url, e)

    return ""


def get_section(link):
    lower = link.lower()

    if "/china/" in lower:
        return "中国"
    if "/world/" in lower:
        return "国际"
    if "/singapore/" in lower:
        return "新加坡"
    if "/finance/" in lower or "/zfinance/" in lower:
        return "财经"

    return "最新"


def fetch_news():
    r = session.get(URL, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = " ".join(a.stripped_strings).strip()
        href = a.get("href", "").strip()

        if len(title) < 6:
            continue

        link = urljoin(BASE, href)

        # 只接受联合早报站内链接
        if not link.startswith(BASE):
            continue

        # 过滤栏目首页
        if "/realtime/" not in link:
            continue

        # 文章通常带 story
        if "story" not in link:
            continue

        # 去掉 URL 参数
        link = link.split("?")[0]

        if link in seen:
            continue

        seen.add(link)

        items.append({
            "title": title,
            "link": link,
            "section": get_section(link),
        })

        # 控制请求数量
        if len(items) >= 80:
            break

    return items


def generate():
    items = fetch_news()

    if not items:
        raise RuntimeError(
            "没有抓取到新闻，联合早报页面结构可能已经改变。"
        )

    print(f"Found {len(items)} articles")

    now = datetime.now(timezone.utc)
    pubdate = format_datetime(now)

    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">',
        "<channel>",
        "<title>联合早报 · 聚合 RSS</title>",
        "<link>https://www.zaobao.com.sg/</link>",
        "<description>联合早报即时新闻聚合</description>",
        "<language>zh-CN</language>",
        f"<lastBuildDate>{pubdate}</lastBuildDate>",
        '<atom:link '
        'href="https://gjw2011.github.io/zaobao-rss/rss.xml" '
        'rel="self" type="application/rss+xml"/>',
    ]

    for i, item in enumerate(items, 1):
        print(
            f"[{i}/{len(items)}] {item['title']}"
        )

        summary = get_summary(item["link"])

        # 避免请求太快
        time.sleep(0.15)

        if summary:
            body = (
                f"<p>{esc(summary)}</p>"
                f'<p><a href="{esc(item["link"])}">'
                "阅读联合早报原文</a></p>"
            )
        else:
            body = (
                f"<p>{esc(item['title'])}</p>"
                f'<p><a href="{esc(item["link"])}">'
                "阅读联合早报原文</a></p>"
            )

        xml.extend([
            "<item>",
            f"<title>{esc(item['title'])}</title>",
            f"<link>{esc(item['link'])}</link>",
            f'<guid isPermaLink="true">'
            f'{esc(item["link"])}</guid>',
            f"<category>{esc(item['section'])}</category>",
            f"<pubDate>{pubdate}</pubDate>",
            f"<description><![CDATA[{cdata(body)}]]>"
            "</description>",
            f"<content:encoded><![CDATA[{cdata(body)}]]>"
            "</content:encoded>",
            "</item>",
        ])

    xml.extend([
        "</channel>",
        "</rss>",
    ])

    os.makedirs("docs", exist_ok=True)

    with open(
        "docs/rss.xml",
        "w",
        encoding="utf-8"
    ) as f:
        f.write("\n".join(xml) + "\n")

    print(f"Generated {len(items)} RSS items")


if __name__ == "__main__":
    generate()
