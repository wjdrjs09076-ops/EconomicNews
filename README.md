# EconomicNews

**국제 경제기관의 새 발표와 보고서를 한 화면에 모으는 경량 뉴스 모니터입니다.** 매크로 리서치에서 원문 출처와 발표 시각을 빠르게 확인하는 데 초점을 맞췄습니다.

**[뉴스 보드 열기](https://wjdrjs09076-ops.github.io/EconomicNews/)** · [수집 코드](docs/scripts/update_news.py) · [갱신 워크플로](.github/workflows/update-news.yml)

## 수집부터 표시까지

`공식 RSS·발표 페이지 → 제목/링크/발표 시각 정리 → 중복·최근 72시간 필터 → 키워드 분류 → 최신 최대 20건 JSON → GitHub Pages`

코드는 Fed, BIS, Bank of England의 RSS와 IMF, OECD, World Bank 발표 페이지/API를 조회합니다. 금리, 물가, 환율, 성장, 무역, 금융안정 등의 분류는 **제목·기관명 키워드 규칙**입니다. 기사 본문의 인과관계 추출, LLM 요약, 투자 신호 생성은 구현하지 않았습니다.

`.github/workflows/update-news.yml`은 5분 간격으로 예약돼 있으며 변경된 `docs/data/latest_news.json`을 커밋합니다. GitHub Actions 예약 작업은 지연·누락될 수 있고, 외부 사이트 구조 변경 시 일부 출처가 비어 있을 수 있습니다. 보드의 시각과 원문 링크를 확인한 뒤 중요한 발표는 반드시 원문에서 재확인해야 합니다.

## 직접 실행

Python 3.11에서 `pip install feedparser` 후 `python docs/scripts/update_news.py`를 실행합니다. 결과는 `docs/data/latest_news.json`에 저장되며, `docs/index.html`이 이를 표시합니다. API 키는 필요하지 않지만 외부 출처 접속이 필요합니다.

