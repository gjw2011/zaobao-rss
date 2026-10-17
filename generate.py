import requests
from bs4 import BeautifulSoup

URLS = [
    "https://www.zaobao.com.sg/node/1128858",
    "https://www.zaobao.com.sg/node/1120916",
    "https://www.zaobao.com.sg/news",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/18.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

for url in URLS:
    print("\n" + "=" * 70)
    print("TEST:", url)

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True
        )

        print("STATUS:", r.status_code)
        print("FINAL URL:", r.url)
        print("HTML LENGTH:", len(r.text))
        print("CONTENT TYPE:", r.headers.get("content-type"))

        soup = BeautifulSoup(r.text, "html.parser")

        print("TITLE:", soup.title.get_text(strip=True)
              if soup.title else "NONE")

        links = []

        for a in soup.find_all("a", href=True):
            text = " ".join(a.stripped_strings).strip()
            href = a.get("href", "").strip()

            if text:
                links.append((text, href))

        print("TOTAL LINKS:", len(links))

        print("\nFIRST 30 LINKS:")
        for text, href in links[:30]:
            print("TEXT:", text[:100])
            print("HREF:", href)
            print("---")

        # 查找 story 链接
        story_links = [
            (text, href)
            for text, href in links
            if "story" in href.lower()
        ]

        print("\nSTORY LINKS:", len(story_links))

        for text, href in story_links[:20]:
            print("STORY:", text[:100])
            print("URL:", href)
            print("---")

        # 查找“阅读更多”
        more_links = [
            (text, href)
            for text, href in links
            if "阅读更多" in text
        ]

        print("\nREAD MORE LINKS:", len(more_links))

        for text, href in more_links[:20]:
            print("READ MORE:", text)
            print("URL:", href)
            print("---")

    except Exception as e:
        print("ERROR:", repr(e))

print("\nDIAGNOSTIC FINISHED")
