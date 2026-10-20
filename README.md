# 🌍 매크로 시황 보드

숫자와 사실만 모은 매크로 대시보드예요. 전망·추천은 넣지 않아요. 색은 한국식(상승 빨강, 하락 파랑).

## 화면

- **지수·금리·위험**: 세계 주요 지수 14개, 미국 금리(2·5·10·30년), 환율, 원자재, VIX·MOVE·OVX, 하이일드·BBB 스프레드, 기대인플레, 실질금리, 장단기 금리차, 시장 폭(RSP − SPY)
- **섹터·대장주**: 미국 섹터 ETF 12개, 섹터별 대장주(섹터 대비 강약), 테마 ETF, 한국 대장주
- **사실 필터 뉴스**: 지난 24시간 뉴스를 사건별로 묶고 라벨을 붙여요

## 검증 라벨

| 라벨 | 뜻 |
|---|---|
| 교차확인 | 시세: 두 출처 종가 차이 0.15% 안 / 뉴스: 서로 다른 언론사 2곳 이상 보도 |
| 단일출처 | 출처가 하나뿐 |
| 상충 | 두 출처 숫자가 달라요 |
| 주장 | 당사자 주장·미확인 보도 |
| 의견 | 전망·추측·질문형 제목 |

출처: 야후(첫 번째), stooq·네이버·FRED(두 번째), 구글 뉴스·CNBC RSS.

## 파일

| 파일 | 하는 일 |
|---|---|
| `config.py` | 종목·지표·뉴스 검색어 목록. **종목 추가·삭제는 여기만** |
| `sources.py` | 바깥 사이트에서 받아 오기 |
| `macro.py` | 계산, 교차확인, 뉴스 분류 |
| `view.py` | 화면(탭마다 함수 하나) |
| `app.py` | 시작 파일. 탭 목록 |
| `brief.py` | 평일 07:40(한국) 디스코드 아침 브리핑 |

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py              # 실제 데이터
MACRO_MOCK=1 streamlit run app.py # 인터넷 없이 가짜 데이터로 화면만
MACRO_MOCK=1 pytest -q            # 테스트
```

**Streamlit Cloud**: share.streamlit.io → Create app → 저장소 `kimgun124-boop/macro-board`, 브랜치 `main`, 파일 `app.py`.

**디스코드 브리핑**: 저장소 Settings → Secrets and variables → Actions → `DISCORD_WEBHOOK_URL` 추가. Actions 탭에서 "매크로 아침 브리핑" → Run workflow로 바로 시험할 수 있어요.
