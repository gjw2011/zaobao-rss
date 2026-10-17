import os
import re
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, SubElement, tostring

import requests
from bs4 import BeautifulSoup


BASE = "https://www.zaobao.com.sg"

# 联合早报栏目
FEEDS = [
    ("最新", "https://www.zaobao.com.sg/realtime"),
    ("新加坡", "https://www.zaobao.com.sg/news/singapore"),
    ("中国", "https://www.zaobao.com.sg/news/china"),
    ("国际", "https://www.zaobao.com.sg/news/world"),
    ("财经", "https://www.zaobao.com.sg/news/biz"),
    ("东南亚", "https://www.zaobao.com.sg/news/sea"),
    ("体育", "https://www.zaobao.com.sg/news/sports"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


session = requests.Session()
session.headers.update(HEADERS)


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_page(url):
    try:
        response = session.get(
            url,
            timeout=30,
            allow_redirects=True
        )

        response.raise_for_status()

        print(
            "GET:",
            response.status_code,
            response.url,
            "LEN:",
            len(response.text)
        )

        return response.text

    except Exception as e:
        print("REQUEST ERROR:", url, repr(e))
        return ""


def collect_article_links():
    articles = {}

    for category, url in FEEDS:

        print()
        print("=" * 70)
        print("CATEGORY:", category)
        print("URL:", url)

        html = get_page(url)

        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):

            href = a.get("href", "").strip()

            title = clean_text(
                " ".join(a.stripped_strings)
            )

            if not href or not title:
                continue

            href = urljoin(BASE, href)

            # 只接受联合早报文章
            if not href.startswith(BASE):
                continue

            # 联合早报文章 URL
            if "/story" not in href:
                continue

            # 排除明显不是文章的链接
            if len(title) < 6:
                continue

            # 去掉 query
            href = href.split("?")[0]

            if href not in articles:

                articles[href] = {
                    "title": title,
                    "category": category,
                }

        print(
            "CURRENT ARTICLE COUNT:",
            len(articles)
        )

    print()
    print("=" * 70)
    print("TOTAL ARTICLE LINKS:", len(articles))

    return list(articles.items())


def extract_title(soup, fallback):

    # 优先 h1
    h1 = soup.find("h1")

    if h1:

        title = clean_text(
            h1.get_text(" ", strip=True)
        )

        if title:
            return title

    # OpenGraph
    og_title = soup.find(
        "meta",
        property="og:title"
    )

    if og_title:

        title = clean_text(
            og_title.get("content", "")
        )

        if title:
            return title

    return fallback


def extract_description(soup):

    # 优先 OpenGraph description
    og = soup.find(
        "meta",
        property="og:description"
    )

    if og:

        text = clean_text(
            og.get("content", "")
        )

        if len(text) > 50:
            return text

    # 常见正文容器
    selectors = [
        "article",
        "[class*='article-content']",
        "[class*='article-body']",
        "[class*='story-content']",
        "[class*='story-body']",
        "[class*='content-body']",
        "[class*='detail-content']",
        "[class*='post-content']",
        "main",
    ]

    containers = []

    for selector in selectors:

        for node in soup.select(selector):

            text = clean_text(
                node.get_text(" ", strip=True)
            )

            if len(text) >= 100:

                containers.append(
                    (len(text), node)
                )

    # 选择正文最长的容器
    if containers:

        containers.sort(
            key=lambda x: x[0],
            reverse=True
        )

        container = containers[0][1]

        paragraphs = []

        for p in container.find_all(
            ["p", "h2", "h3"]
        ):

            text = clean_text(
                p.get_text(" ", strip=True)
            )

            if len(text) < 12:
                continue

            # 去除导航和页面噪音
            bad_words = [
                "上一篇",
                "下一篇",
                "延伸阅读",
                "相关新闻",
                "订阅",
                "登录",
                "版权所有",
                "新闻速递",
                "立即订阅",
            ]

            if any(
                word in text
                for word in bad_words
            ):
                continue

            if text not in paragraphs:
                paragraphs.append(text)

        if paragraphs:

            return "\n\n".join(
                paragraphs[:100]
            )

        # 如果没有 p，直接取容器文本
        text = clean_text(
            container.get_text(
                "\n",
                strip=True
            )
        )

        if len(text) >= 80:
            return text[:10000]

    # 最后的备用方案
    # 从整个页面提取文本
    body = soup.body

    if body:

        text = clean_text(
            body.get_text(
                " ",
                strip=True
            )
        )

        # 删除过短内容
        if len(text) >= 80:

            return text[:10000]

    return ""


def extract_pub_date(soup):

    # time 标签
    time_tag = soup.find("time")

    if time_tag:

        value = time_tag.get(
            "datetime"
        )

        if value:

            try:

                return datetime.fromisoformat(
                    value.replace(
                        "Z",
                        "+00:00"
                    )
                )

            except Exception:
                pass

    # meta article:published_time
    meta = soup.find(
        "meta",
        property="article:published_time"
    )

    if meta:

        value = meta.get(
            "content",
            ""
        )

        try:

            return datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

        except Exception:
            pass

    # 搜索中文发布时间
    text = soup.get_text(
        " ",
        strip=True
    )

    patterns = [
        r"发布[：:\s]*/?\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})",
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            try:

                return datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                    int(match.group(5)),
                    tzinfo=timezone.utc
                )

            except Exception:
                pass

    return datetime.now(
        timezone.utc
    )


def parse_article(url, meta):

    print()
    print("-" * 70)
    print("ARTICLE:")
    print(url)

    html = get_page(url)

    if not html:
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    title = extract_title(
        soup,
        meta["title"]
    )

    description = extract_description(
        soup
    )

    pub_date = extract_pub_date(
        soup
    )

    print("TITLE:", title)
    print(
        "CONTENT LENGTH:",
        len(description)
    )

    if len(description) < 40:

        print(
            "SKIP: ARTICLE CONTENT TOO SHORT"
        )

        return None

    return {
        "title": title,
        "link": url,
        "description": description,
        "category": meta["category"],
        "pub_date": pub_date,
    }


def create_rss(items):

    rss = Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:content":
                "http://purl.org/rss/1.0/modules/content/"
        }
    )

    channel = SubElement(
        rss,
        "channel"
    )

    SubElement(
        channel,
        "title"
    ).text = "联合早报 RSS"

    SubElement(
        channel,
        "link"
    ).text = BASE

    SubElement(
        channel,
        "description"
    ).text = "联合早报新闻 RSS"

    SubElement(
        channel,
        "language"
    ).text = "zh-CN"

    SubElement(
        channel,
        "lastBuildDate"
    ).text = format_datetime(
        datetime.now(timezone.utc)
    )

    for item in items[:50]:

        node = SubElement(
            channel,
            "item"
        )

        SubElement(
            node,
            "title"
        ).text = item["title"]

        SubElement(
            node,
            "link"
        ).text = item["link"]

        SubElement(
            node,
            "guid",
            {
                "isPermaLink": "true"
            }
        ).text = item["link"]

        SubElement(
            node,
            "pubDate"
        ).text = format_datetime(
            item["pub_date"]
        )

        SubElement(
            node,
            "category"
        ).text = item["category"]

        description = SubElement(
            node,
            "description"
        )

        description.text = item[
            "description"
        ]

        content = SubElement(
            node,
            "{http://purl.org/rss/1.0/modules/content/}encoded"
        )

        content.text = item[
            "description"
        ]

    return tostring(
        rss,
        encoding="utf-8",
        xml_declaration=True
    )


def main():

    print()
    print("=" * 70)
    print("ZAOBAO RSS GENERATOR")
    print("=" * 70)

    links = collect_article_links()

    if not links:

        print(
            "ERROR: NO ARTICLE LINKS FOUND"
        )

        raise SystemExit(1)

    items = []

    # 最多抓 80 篇文章
    for index, (url, meta) in enumerate(
        links[:80],
        start=1
    ):

        print()
        print(
            f"PROCESS {index}/{min(80, len(links))}"
        )

        try:

            item = parse_article(
                url,
                meta
            )

            if item:

                items.append(item)

        except Exception as e:

            print(
                "ARTICLE PARSE ERROR:",
                repr(e)
            )

        time.sleep(0.2)

    # 按时间排序
    items.sort(
        key=lambda x: x["pub_date"],
        reverse=True
    )

    # URL 去重
    unique = []
    seen = set()

    for item in items:

        if item["link"] in seen:
            continue

        seen.add(
            item["link"]
        )

        unique.append(item)

    print()
    print("=" * 70)
    print(
        "FINAL RSS ITEMS:",
        len(unique)
    )

    if not unique:

        print(
            "ERROR: NO VALID ARTICLES"
        )

        raise SystemExit(1)

    os.makedirs(
        "docs",
        exist_ok=True
    )

    rss_data = create_rss(
        unique
    )

    output = "docs/rss.xml"

    with open(
        output,
        "wb"
    ) as f:

        f.write(
            rss_data
        )

    print(
        "RSS GENERATED:",
        output
    )

    print(
        "RSS SIZE:",
        len(rss_data),
        "bytes"
    )

    print("=" * 70)
    print("DONE")


if __name__ == "__main__":
    main()
