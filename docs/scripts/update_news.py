import json
import os
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import feedparser

OUT_PATH = "docs/data/latest_news.json"
MAX_ITEMS = 5
TIMEOUT_SEC = 20

# ✅ 반드시 포함: IMF / Fed / World Bank
# - Fed: RSS 피드 페이지에서 제공되는 press releases feed 사용 :contentReference[oaicite:0]{index=0}
# - World Bank: World Bank 뉴스 페이지에 노출되는 search.worldbank.org API 사용 :contentReference[oaicite:1]{index=1}
# - IMF: IMF Media Center의 newslisting 페이지(HTML)에서 링크를 추출 :contentReference[oaicite:2]{index=2}
SOURCES = {
    "FED_RSS": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ECB_RSS": "https://www.ecb.europa.eu/rss/press.html",  # ECB RSS 안내 페이지 :contentReference[oaicite:3]{index=3}
    "WORLD_BANK_API": "https://search.worldbank.org/api/v2/news?format=json&rows=20&lang_exact=English&os=0",
    "IMF_MEDIA_LISTING": "https://mediacenter.imf.org/newslisting",
}

def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def http_get(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (GitHub Actions bot)"})
    with urlopen(req, timeout=TIMEOUT_SEC) as resp:
        return resp.read().decode("utf-8", errors="replace")

def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def try_parse_entry_time(e) -> str | None:
    # feedparser의 *_parsed가 있으면 UTC로 변환
    t = None
    if getattr(e, "published_parsed", None):
        t = e.published_parsed
    elif getattr(e, "updated_parsed", None):
        t = e.updated_parsed
    if not t:
        return None
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return dt.replace(microsecond=0).isoformat()

def add_item(items, title, source, link, published_utc=None):
    title = norm_space(title)
    source = norm_space(source)
    link = (link or "").strip()

    if not title or not link:
        return
    items.append({
        "title": title,
        "source": source if source else "Unknown",
        "link": link,
        "published_utc": published_utc
    })

def collect_fed(items):
    feed = feedparser.parse(SOURCES["FED_RSS"])
    for e in feed.entries[:30]:
        add_item(items, e.get("title"), "Federal Reserve", e.get("link"), try_parse_entry_time(e))

def collect_ecb(items):
    # ECB press RSS 목록 (페이지 자체가 RSS 목록/리디렉션을 제공) :contentReference[oaicite:4]{index=4}
    feed = feedparser.parse(SOURCES["ECB_RSS"])
    for e in feed.entries[:30]:
        add_item(items, e.get("title"), "ECB", e.get("link"), try_parse_entry_time(e))

def collect_world_bank(items):
    # World Bank 뉴스 페이지에서 공개 API 엔드포인트가 노출됨 :contentReference[oaicite:5]{index=5}
    try:
        raw = http_get(SOURCES["WORLD_BANK_API"])
        data = json.loads(raw)
        docs = data.get("documents") or {}
        # dict 형태로 오는 경우가 많음
        for _, d in list(docs.items())[:30]:
            title = d.get("title") or ""
            link = d.get("url") or d.get("link") or ""
            pub = d.get("date") or d.get("pubdate") or d.get("updated")
            add_item(items, title, "World Bank", link, str(pub) if pub else None)
    except Exception:
        pass

def collect_imf(items):
    # IMF Media Center newslisting은 HTML 페이지로 제공됨 :contentReference[oaicite:6]{index=6}
    # 여기서 View Story 링크를 추출해 제목을 근처 텍스트로 구성(단순/안정형)
    try:
        html = http_get(SOURCES["IMF_MEDIA_LISTING"])

        # View Story 링크가 포함된 경로(/news/...)를 우선 추출
        links = re.findall(r'href="([^"]+/news/[^"]+)"', html)
        seen = set()
        for href in links:
            if href.startswith("/"):
                link = "https://mediacenter.imf.org" + href
            elif href.startswith("http"):
                link = href
            else:
                continue

            if link in seen:
                continue
            seen.add(link)

            # 링크 주변 텍스트에서 IMF / ... 패턴으로 제목 후보 추출
            idx = html.find(href)
            window = html[max(0, idx - 400): idx + 400]
            m = re.search(r'IMF\s*/\s*[^<\n\r]{5,140}', window)
            title = m.group(0) if m else "IMF update"

            add_item(items, title, "IMF", link, None)

            if len(seen) >= 15:
                break
    except Exception:
        pass

def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    items = []
    collect_imf(items)
    collect_fed(items)
    collect_world_bank(items)
    collect_ecb(items)

    # 중복 제거(링크 기준)
    dedup = []
    seen_links = set()
    for it in items:
        if it["link"] in seen_links:
            continue
        seen_links.add(it["link"])
        dedup.append(it)

    # 정렬: published_utc 있는 항목 우선 + 최신으로(문자열 정렬이 불안하면 None을 뒤로)
    def key(it):
        return (0, it["published_utc"]) if it["published_utc"] else (1, "")
    dedup.sort(key=key, reverse=True)

    out = {
        "generated_at_utc": utc_now_iso(),
        "items": dedup[:MAX_ITEMS]
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
