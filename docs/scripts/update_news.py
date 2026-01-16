import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

import feedparser

OUT_PATH = "docs/data/latest_news.json"
MAX_ITEMS = 20
LOOKBACK_HOURS = 24
TIMEOUT_SEC = 25

SOURCES = {
    # ✅ Fed: 공식 RSS 안내 페이지 존재. :contentReference[oaicite:0]{index=0}
    "FED_PRESS_RSS": "https://www.federalreserve.gov/feeds/press_all.xml",

    # ✅ BIS: 공식 RSS 목록에 press releases feed 제공. :contentReference[oaicite:1]{index=1}
    "BIS_PRESS_RSS": "https://www.bis.org/doclist/all_pressrels.rss",

    # ✅ BoE: RSS 메인 페이지(News/Publ/Speeches 등) 제공. :contentReference[oaicite:2]{index=2}
    # (도구가 해당 RSS를 400으로 못 열어도, 브라우저/액션에서는 대체로 정상 동작합니다)
    "BOE_NEWS_RSS": "https://www.bankofengland.co.uk/rss/news",
    "BOE_PUBLICATIONS_RSS": "https://www.bankofengland.co.uk/rss/publications",
    "BOE_SPEECHES_RSS": "https://www.bankofengland.co.uk/rss/speeches",

    # ✅ OECD: RSS가 일관되지 않아, “Latest news releases”가 있는 공식 페이지를 HTML로 스크랩합니다. :contentReference[oaicite:3]{index=3}
    "OECD_STATS_RELEASES_PAGE": "https://www.oecd.org/en/data/insights/statistical-releases/2024/01/release-dates-for-oecd-statistics-news-releases.html",

    # ✅ IMF: Media Center newslisting 사용. :contentReference[oaicite:4]{index=4}
    "IMF_NEWSLISTING": "https://mediacenter.imf.org/newslisting?category=news",

    # ✅ World Bank: 공식 News 페이지에 press release용 search API(v2/news) 엔드포인트가 노출됩니다. :contentReference[oaicite:5]{index=5}
    "WORLD_BANK_PRESS_API": "https://search.worldbank.org/api/v2/news?format=json&rows=50&lang_exact=English&displayconttype_exact=Press%20Release&os=0",
}

CATEGORY_RULES = {
    "rates": [
        "rate", "interest", "bank rate", "policy rate", "cut", "hike", "tighten", "easing", "monetary",
        "금리", "기준금리", "인상", "인하", "통화정책"
    ],
    "inflation": [
        "inflation", "cpi", "prices", "price pressures", "disinflation",
        "물가", "인플레이션", "cpi"
    ],
    "fx": [
        "fx", "foreign exchange", "currency", "usd", "dollar", "yen", "euro", "sterling",
        "환율", "달러", "엔화", "유로"
    ],
    "growth": [
        "gdp", "growth", "recession", "soft landing", "expansion", "contraction",
        "성장", "gdp", "경기침체"
    ],
    "trade": [
        "trade", "tariff", "export", "import", "sanction", "supply chain",
        "무역", "관세", "수출", "수입", "제재", "공급망"
    ],
    "financial_stability": [
        "bank", "liquidity", "stress", "credit", "default", "systemic", "financial stability",
        "은행", "유동성", "신용", "부실", "금융안정"
    ],
    "institutions": [
        "imf", "world bank", "oecd", "bis", "federal reserve", "bank of england",
        "IMF", "World Bank", "OECD", "BIS", "Fed", "BoE"
    ],
}

def utc_now():
    return datetime.now(timezone.utc)

def iso(dt: datetime):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()

def http_get(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (GitHub Actions bot)"})
    with urlopen(req, timeout=TIMEOUT_SEC) as resp:
        return resp.read().decode("utf-8", errors="replace")

def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def parse_feed_time(entry) -> datetime | None:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    return datetime(*t[:6], tzinfo=timezone.utc)

def categorize(title: str, source: str) -> list[str]:
    text = (title or "") + " " + (source or "")
    text_low = text.lower()
    cats = []
    for cat, kws in CATEGORY_RULES.items():
        if any(kw.lower() in text_low for kw in kws):
            cats.append(cat)
    return cats or ["other"]

def add_item(items: list, title: str, source: str, link: str, published_dt: datetime | None):
    title = norm_space(title)
    source = norm_space(source)
    link = (link or "").strip()
    if not title or not link:
        return

    items.append({
        "title": title,
        "source": source if source else "Unknown",
        "link": link,
        "published_utc": iso(published_dt) if published_dt else None,
        "categories": categorize(title, source),
    })

def collect_rss(items: list, url: str, source_name: str, limit: int = 50):
    feed = feedparser.parse(url)
    for e in feed.entries[:limit]:
        add_item(items, e.get("title", ""), source_name, e.get("link", ""), parse_feed_time(e))

def collect_imf(items: list):
    # IMF Media Center는 RSS가 아니라 listing HTML 기반. :contentReference[oaicite:6]{index=6}
    try:
        html = http_get(SOURCES["IMF_NEWSLISTING"])

        # date 패턴(예: 17 Oct 2025) / 링크(/news/...)를 함께 잡기
        # 링크는 보통 /news/xxxxx 형태
        links = re.findall(r'href="([^"]+/news/[^"]+)"', html)
        # 제목 후보는 "IMF / ..." 텍스트를 우선 시도
        # 날짜는 "dd Mon yyyy" 패턴 우선
        date_re = re.compile(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})')
        seen = set()

        for href in links:
            link = href
            if link.startswith("/"):
                link = "https://mediacenter.imf.org" + link
            if link in seen:
                continue
            seen.add(link)

            idx = html.find(href)
            window = html[max(0, idx - 500): idx + 500]

            m_title = re.search(r'IMF\s*/\s*[^<\n\r]{8,160}', window)
            title = m_title.group(0) if m_title else "IMF update"

            m_date = date_re.search(window)
            published_dt = None
            if m_date:
                try:
                    published_dt = datetime.strptime(m_date.group(1), "%d %b %Y").replace(tzinfo=timezone.utc)
                except Exception:
                    published_dt = None

            add_item(items, title, "IMF", link, published_dt)

            if len(seen) >= 20:
                break
    except Exception:
        pass

def collect_world_bank(items: list):
    # World Bank News 페이지에 press release용 search API endpoint가 노출됩니다. :contentReference[oaicite:7]{index=7}
    try:
        raw = http_get(SOURCES["WORLD_BANK_PRESS_API"])
        data = json.loads(raw)
        docs = data.get("documents") or {}
        for _, d in list(docs.items())[:60]:
            title = d.get("title") or ""
            link = d.get("url") or d.get("link") or ""
            # date는 문자열로 오는 경우가 많아서 파싱 시도
            published_dt = None
            dt_str = d.get("date") or d.get("pub_date") or d.get("updated") or d.get("docdt")
            if dt_str:
                # 다양한 형식을 안전하게 커버(YYYY-MM-DD, ISO 등)
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
                    try:
                        published_dt = datetime.strptime(str(dt_str)[:len(fmt)], fmt)
                        if published_dt.tzinfo is None:
                            published_dt = published_dt.replace(tzinfo=timezone.utc)
                        else:
                            published_dt = published_dt.astimezone(timezone.utc)
                        break
                    except Exception:
                        continue
            add_item(items, title, "World Bank", link, published_dt)
    except Exception:
        pass

def collect_oecd(items: list):
    # OECD “Latest news releases” 섹션이 있는 공식 페이지에서 HTML로 제목/날짜/링크 스크랩. :contentReference[oaicite:8]{index=8}
    try:
        html = http_get(SOURCES["OECD_STATS_RELEASES_PAGE"])

        # "Latest news releases" 이후의 링크들만 대충 추출
        anchor_start = html.lower().find("latest news releases")
        if anchor_start == -1:
            anchor_start = 0
        snippet = html[anchor_start: anchor_start + 120000]

        # /en/.../statistical-releases/... 링크를 우선적으로 뽑기
        links = re.findall(r'href="([^"]+/en/data/insights/statistical-releases/[^"]+)"', snippet)
        seen = set()
        for href in links:
            link = href
            if link.startswith("/"):
                link = "https://www.oecd.org" + link
            if link in seen:
                continue
            seen.add(link)

            # 링크 주변에서 날짜 패턴 찾기(예: 15 January 2026)
            idx = snippet.find(href)
            win = snippet[max(0, idx - 400): idx + 500]

            # 제목은 링크 텍스트가 HTML에 섞여 있어서, 근처의 title-ish 텍스트를 대충 잡음
            # 가장 안전하게는 href 마지막 슬러그를 제목 후보로 쓰되, 사람이 보기 좋게 처리
            slug = link.rstrip("/").split("/")[-1]
            title_guess = slug.replace("-", " ").strip()
            title_guess = title_guess[:120] if title_guess else "OECD statistical release"

            m_date = re.search(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})', win)
            published_dt = None
            if m_date:
                try:
                    published_dt = datetime.strptime(m_date.group(1), "%d %B %Y").replace(tzinfo=timezone.utc)
                except Exception:
                    published_dt = None

            add_item(items, title_guess, "OECD", link, published_dt)

            if len(seen) >= 15:
                break
    except Exception:
        pass

def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    items = []

    # ✅ 필수 기관
    collect_imf(items)
    collect_world_bank(items)
    collect_rss(items, SOURCES["FED_PRESS_RSS"], "Federal Reserve", limit=50)

    # ✅ 출처 확장(추가 3개)
    collect_rss(items, SOURCES["BIS_PRESS_RSS"], "BIS", limit=50)
    collect_rss(items, SOURCES["BOE_NEWS_RSS"], "Bank of England", limit=50)
    collect_rss(items, SOURCES["BOE_PUBLICATIONS_RSS"], "Bank of England", limit=50)
    collect_rss(items, SOURCES["BOE_SPEECHES_RSS"], "Bank of England", limit=50)
    collect_oecd(items)

    # 1) 링크 기준 중복 제거
    dedup = []
    seen_links = set()
    for it in items:
        if it["link"] in seen_links:
            continue
        seen_links.add(it["link"])
        dedup.append(it)

    # 2) 최근 24시간만 남기기(시간 없는 항목은 뒤로 보내되 일단 유지)
    cutoff = utc_now() - timedelta(hours=LOOKBACK_HOURS)

    recent = []
    unknown_time = []
    for it in dedup:
        if it["published_utc"]:
            try:
                dt = datetime.fromisoformat(it["published_utc"].replace("Z", "+00:00")).astimezone(timezone.utc)
                if dt >= cutoff:
                    recent.append((dt, it))
            except Exception:
                unknown_time.append(it)
        else:
            unknown_time.append(it)

    recent.sort(key=lambda x: x[0], reverse=True)
    sorted_items = [it for _, it in recent] + unknown_time

    # 3) 최대 20개
    out = {
        "generated_at_utc": iso(utc_now()),
        "lookback_hours": LOOKBACK_HOURS,
        "items": sorted_items[:MAX_ITEMS],
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
