"""지켜볼 종목·지표 목록. 종목을 넣고 빼려면 이 파일만 고치면 돼요.

- yf: 야후 티커(첫 번째 출처)
- stooq: 두 번째 출처 티커(없으면 '단일출처'로 표시). 미국 종목·ETF는 자동으로 '티커.us'를 써요.
- fred: 미국 연준(FRED) 시리즈 id. 금리는 야후 값과 FRED 값을 맞춰 봐요.
"""

INDICES = [
    {"name": "S&P 500", "yf": "^GSPC", "stooq": "^spx", "region": "미국"},
    {"name": "나스닥 종합", "yf": "^IXIC", "stooq": "^ndq", "region": "미국"},
    {"name": "다우존스", "yf": "^DJI", "stooq": "^dji", "region": "미국"},
    {"name": "러셀 2000", "yf": "^RUT", "stooq": None, "region": "미국"},
    {"name": "코스피", "yf": "^KS11", "stooq": None, "region": "한국", "naver": "KOSPI"},
    {"name": "코스닥", "yf": "^KQ11", "stooq": None, "region": "한국", "naver": "KOSDAQ"},
    {"name": "닛케이 225", "yf": "^N225", "stooq": "^nkx", "region": "일본"},
    {"name": "대만 가권", "yf": "^TWII", "stooq": None, "region": "대만"},
    {"name": "상하이종합", "yf": "000001.SS", "stooq": "^shc", "region": "중국"},
    {"name": "항셍", "yf": "^HSI", "stooq": "^hsi", "region": "홍콩"},
    {"name": "인도 니프티", "yf": "^NSEI", "stooq": None, "region": "인도"},
    {"name": "독일 DAX", "yf": "^GDAXI", "stooq": "^dax", "region": "유럽"},
    {"name": "유로스톡스 50", "yf": "^STOXX50E", "stooq": None, "region": "유럽"},
    {"name": "영국 FTSE", "yf": "^FTSE", "stooq": "^ukx", "region": "유럽"},
]

# kind: rate(금리, 변화는 %p) · fx · commodity · crypto
MACRO = [
    {"name": "미국 2년물", "yf": None, "kind": "rate", "group": "금리", "fred": "DGS2"},
    {"name": "미국 5년물", "yf": "^FVX", "kind": "rate", "group": "금리", "fred": "DGS5"},
    {"name": "미국 10년물", "yf": "^TNX", "kind": "rate", "group": "금리", "fred": "DGS10"},
    {"name": "미국 30년물", "yf": "^TYX", "kind": "rate", "group": "금리", "fred": "DGS30"},
    {"name": "달러인덱스", "yf": "DX-Y.NYB", "kind": "fx", "group": "환율"},
    {"name": "원/달러", "yf": "KRW=X", "kind": "fx", "group": "환율", "stooq": "usdkrw"},
    {"name": "엔/달러", "yf": "JPY=X", "kind": "fx", "group": "환율", "stooq": "usdjpy"},
    {"name": "유로/달러", "yf": "EURUSD=X", "kind": "fx", "group": "환율", "stooq": "eurusd"},
    {"name": "WTI", "yf": "CL=F", "kind": "commodity", "group": "원자재", "unit": "$"},
    {"name": "브렌트", "yf": "BZ=F", "kind": "commodity", "group": "원자재", "unit": "$"},
    {"name": "금", "yf": "GC=F", "kind": "commodity", "group": "원자재", "unit": "$"},
    {"name": "구리", "yf": "HG=F", "kind": "commodity", "group": "원자재", "unit": "$"},
    {"name": "천연가스", "yf": "NG=F", "kind": "commodity", "group": "원자재", "unit": "$"},
    {"name": "비트코인", "yf": "BTC-USD", "kind": "crypto", "group": "원자재", "unit": "$"},
]

# 변동성 지수는 야후, 신용·물가·실질금리는 FRED
VOL = [
    {"name": "VIX (주식 변동성)", "yf": "^VIX", "read": "20 위면 주식시장 불안이 큰 편, 30 위면 매우 큰 편"},
    {"name": "MOVE (채권 변동성)", "yf": "^MOVE", "read": "미 국채 옵션 내재변동성. 100 위면 채권 불안이 큰 편"},
    {"name": "OVX (원유 변동성)", "yf": "^OVX", "read": "WTI 옵션 내재변동성"},
]
FRED = [
    {"name": "하이일드 스프레드", "id": "BAMLH0A0HYM2", "group": "신용", "read": "하이일드 회사채 − 국채 금리. 오르면 신용 위험을 더 높게 본다는 뜻"},
    {"name": "BBB 회사채 스프레드", "id": "BAMLC0A4CBBB", "group": "신용", "read": "투자등급 하단 회사채 − 국채 금리"},
    {"name": "10년 기대인플레(BEI)", "id": "T10YIE", "group": "물가·실질금리", "read": "10년 명목금리 − 물가연동채 금리"},
    {"name": "10년 실질금리(TIPS)", "id": "DFII10", "group": "물가·실질금리", "read": "물가 영향을 뺀 10년 금리"},
    {"name": "장단기 금리차(10Y−2Y)", "id": "T10Y2Y", "group": "물가·실질금리", "read": "음수면 장단기 금리 역전"},
]

SECTORS = [
    ("XLK", "기술"), ("XLC", "커뮤니케이션"), ("XLY", "경기소비재"), ("XLP", "필수소비재"), ("XLE", "에너지"),
    ("XLF", "금융"), ("XLV", "헬스케어"), ("XLI", "산업재"), ("XLB", "소재"), ("XLRE", "부동산"),
    ("XLU", "유틸리티"), ("SMH", "반도체"),
]
# 섹터 ETF → 대장주(시가총액 상위 위주)
LEADERS = {
    "SMH": [("NVDA", "엔비디아"), ("TSM", "TSMC"), ("AVGO", "브로드컴"), ("MU", "마이크론"), ("AMD", "AMD")],
    "XLK": [("AAPL", "애플"), ("MSFT", "마이크로소프트"), ("ORCL", "오라클"), ("PLTR", "팔란티어")],
    "XLC": [("GOOGL", "알파벳"), ("META", "메타"), ("NFLX", "넷플릭스")],
    "XLY": [("AMZN", "아마존"), ("TSLA", "테슬라"), ("HD", "홈디포")],
    "XLP": [("WMT", "월마트"), ("COST", "코스트코"), ("PG", "P&G")],
    "XLE": [("XOM", "엑슨모빌"), ("CVX", "셰브론")],
    "XLF": [("JPM", "JP모건"), ("BRK-B", "버크셔"), ("V", "비자")],
    "XLV": [("LLY", "일라이릴리"), ("UNH", "유나이티드헬스"), ("JNJ", "존슨앤존슨")],
    "XLI": [("GE", "GE에어로스페이스"), ("CAT", "캐터필러"), ("VRT", "버티브")],
    "XLB": [("LIN", "린데")],
    "XLRE": [("PLD", "프롤로지스")],
    "XLU": [("NEE", "넥스트에라"), ("CEG", "컨스텔레이션"), ("VST", "비스트라")],
}
THEMES = [
    ("EWY", "한국"), ("DRAM", "메모리"), ("MAGS", "M7"), ("XBI", "바이오"), ("IWO", "소형 성장"), ("EEM", "신흥국"),
    ("LIT", "리튬·배터리"), ("URA", "우라늄·원전"), ("GRID", "전력망"), ("ITA", "미 방산"), ("SHLD", "방산테크"),
    ("TAN", "태양광"), ("FAN", "풍력"), ("JETS", "항공"), ("XRT", "소매"), ("IVE", "S&P 가치주"), ("DVY", "고배당"),
    ("RSP", "S&P 동일가중"), ("SPY", "S&P 500"),
]
# 한국 대장주: 네이버 일봉(장중 갱신)
KR_LEADERS = [
    ("005930", "삼성전자", "반도체"), ("000660", "SK하이닉스", "반도체"), ("373220", "LG에너지솔루션", "2차전지"),
    ("207940", "삼성바이오로직스", "바이오"), ("005380", "현대차", "자동차"), ("034020", "두산에너빌리티", "원전·전력"),
    ("012450", "한화에어로스페이스", "방산"), ("267260", "HD현대일렉트릭", "전력기기"), ("105560", "KB금융", "금융"),
]

# 뉴스 검색어(구글 뉴스, 지난 24시간)
NEWS_QUERIES = [
    ("en", "stock market close S&P 500 Nasdaq"), ("en", "Federal Reserve rates Treasury yields"),
    ("en", "oil prices Brent WTI"), ("en", "semiconductor stocks Nvidia memory"),
    ("en", "Iran Strait of Hormuz"), ("en", "CPI inflation jobs report"),
    ("ko", "코스피 마감"), ("ko", "원달러 환율"), ("ko", "반도체 수출"),
]
# 외신(뉴욕타임스·WSJ·FT·이코노미스트 등): 구글 뉴스에서 언론사 사이트로 좁혀 검색
NEWS_QUERIES += [
    ("en", "site:nytimes.com economy OR markets OR stocks"), ("en", "site:wsj.com markets OR economy"),
    ("en", "site:ft.com markets OR economy"), ("en", "site:reuters.com markets"),
    ("en", "site:bloomberg.com markets"), ("en", "site:economist.com finance economics"),
    ("en", "site:apnews.com stocks OR economy"),
]
DIRECT_FEEDS = [
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("The New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("The New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"),
    ("The Wall Street Journal", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("The Economist", "https://www.economist.com/finance-and-economics/rss.xml"),
    ("Financial Times", "https://www.ft.com/markets?format=rss"),
]
# '주요 외신'으로 따로 세는 언론사(구글 뉴스 표기 기준)
MAJOR_PRESS = {"Reuters", "Bloomberg", "Bloomberg.com", "The New York Times", "The Wall Street Journal", "WSJ",
               "Financial Times", "The Economist", "AP News", "Associated Press", "CNBC", "MarketWatch", "Barron's",
               "Nikkei Asia", "연합뉴스", "Yonhap News Agency"}

# ─────────────────────────── 이슈 ↔ 섹터 ───────────────────────────
# words: 뉴스 제목에서 이 이슈를 찾는 단어(정규식, 대소문자 무시)
# driver: 이 이슈를 숫자로 보여 주는 지표(첫 번째가 기준)
# links: (티커, same|opposite, 이유) — driver가 오를 때 같이 오를지(same) 반대일지(opposite).
#        이유는 보내 주신 블로그·리포트에서 나온 '가설'이에요. 맞는지는 화면에서 실제 등락으로 확인해요.
ISSUES = [
    {"key": "oil", "name": "중동·이란·유가", "words": r"iran|hormuz|israel|saudi|houthi|opec|crude|brent|wti|oil price|이란|호르무즈|중동|유가|사우디",
     "driver": ["CL=F", "^OVX"],
     "links": [("XLE", "same", "유가가 오르면 에너지 기업 이익이 늘어요"),
               ("ITA", "same", "전쟁·재고 보충 수요(휴전 때도 '재고 보충' 내러티브)"),
               ("JETS", "opposite", "항공은 연료비 부담"),
               ("XLY", "opposite", "기름값이 소비 여력을 깎아요"),
               ("^TNX", "same", "유가↑→물가↑→금리↑ 경로. 블로그 관찰: 최근엔 금리가 유가에 잘 반응하지 않음(면역)")]},
    {"key": "rates", "name": "금리·연준", "words": r"federal reserve|\bfed\b|fomc|powell|treasury|yields?|rate cut|rate hike|bond market|금리|연준|파월|국채|기준금리",
     "driver": ["^TNX", "fred:DGS2"],
     "links": [("XLRE", "opposite", "금리가 오르면 부동산 할인율·조달비용 부담"),
               ("XLU", "opposite", "유틸리티는 채권 대체재라 금리에 약해요"),
               ("XLF", "same", "금리가 오르면 은행 예대마진 개선"),
               ("IWO", "opposite", "소형 성장주는 금리에 민감"),
               ("XLK", "opposite", "먼 미래 이익의 현재가치가 줄어요(실적이 이기면 예외)")]},
    {"key": "macro", "name": "물가·고용 지표", "words": r"\bcpi\b|inflation|\bpce\b|payrolls?|jobs report|unemployment|jobless|retail sales|\bgdp\b|물가|고용|실업|소비자물가",
     "driver": ["^TNX", "DX-Y.NYB"],
     "links": [("XLK", "opposite", "물가가 뜨거우면 금리↑ → 기술주 부담"),
               ("XLP", "same", "불안할 때 필수소비재로 피신"),
               ("IWO", "opposite", "금리 민감 소형 성장주")]},
    {"key": "ai", "name": "AI·반도체", "words": r"nvidia|\bai\b|artificial intelligence|semiconductor|chips?|\bhbm\b|memory|micron|hynix|samsung|tsmc|data ?center|capex|openai|반도체|하이닉스|삼성전자|엔비디아|데이터센터",
     "driver": ["SMH", "DRAM"],
     "links": [("XLK", "same", "AI 캐펙스가 기술 섹터 이익을 끌어요"),
               ("GRID", "same", "데이터센터 전력 수요 → 전력망"),
               ("URA", "same", "데이터센터 전력 → 원전·우라늄"),
               ("XLU", "same", "전력 판매(CEG·VST) 수혜"),
               ("EWY", "same", "한국 지수는 삼성전자·SK하이닉스 비중이 커요")]},
    {"key": "tariff", "name": "관세·무역", "words": r"tariffs?|trade war|trade deal|export controls?|sanctions?|관세|무역|수출 ?규제|수출통제",
     "driver": ["DX-Y.NYB", "EEM"],
     "links": [("EEM", "opposite", "달러 강세·무역 갈등은 신흥국에 부담"),
               ("EWY", "opposite", "수출 비중이 큰 한국"),
               ("XLI", "opposite", "공급망 비용↑"),
               ("XRT", "opposite", "수입품 가격↑ → 소매 마진 부담")]},
    {"key": "power", "name": "전력·원전 인프라", "words": r"power grid|electricity|nuclear|uranium|\bsmr\b|utilit|transformer|전력|원전|변압기|송전|ESS",
     "driver": ["GRID", "URA"],
     "links": [("XLU", "same", "전력 수요 증가"), ("XLI", "same", "전력기기·건설 수주"),
               ("TAN", "same", "신재생 같이 묶이는 날이 많아요")]},
    {"key": "defense", "name": "방산·지정학", "words": r"defen[cs]e|missile|nato|ukraine|russia|ceasefire|military|pentagon|방산|휴전|우크라이나|러시아|미사일",
     "driver": ["ITA", "SHLD"],
     "links": [("XLE", "same", "지정학 위험 → 에너지 공급 우려"), ("^VIX", "same", "위험 회피")]},
    {"key": "bio", "name": "헬스케어·바이오", "words": r"\bfda\b|biotech|pharma|drug ?makers?|eli lilly|obesity|glp-1|medicare|바이오|제약|신약",
     "driver": ["XBI", "XLV"],
     "links": [("IWO", "same", "바이오는 소형 성장주 비중이 커요"),
               ("SMH", "opposite", "반도체에서 빠진 돈이 헬스케어로 도는 순환매(블로그 관찰)")]},
    {"key": "korea", "name": "한국 시장", "words": r"kospi|kosdaq|korea|korean won|코스피|코스닥|원화|원달러|외국인",
     "driver": ["^KS11", "KRW=X"],
     "links": [("EWY", "same", "미국에 상장된 한국 ETF"),
               ("KRW=X", "opposite", "원/달러가 오르면(원화 약세) 외국인 매도 압력")]},
    {"key": "credit", "name": "신용·유동성", "words": r"credit|default|private credit|junk|high.yield|bankrupt|liquidity|신용|부도|유동성|회사채",
     "driver": ["fred:BAMLH0A0HYM2"],
     "links": [("XLF", "opposite", "신용 위험↑ → 금융주 부담"), ("IWO", "opposite", "자금 조달이 어려운 소형주"),
               ("^GSPC", "opposite", "하이퍼스케일러 '숨은 부채' 이슈 때문에 스프레드를 봐요(블로그)")]},
]

# ─────────────────────────── 경제지표(FRED) ───────────────────────────
# how: yoy(전년 대비 %) · mom(전월 대비 %) · diff(전월 대비 증감) · level(값 그대로)
# release: 발표 일정 규칙(fred_api_key가 있으면 FRED 발표일, 없으면 이 규칙으로 추정)
ECON = [
    {"id": "CPIAUCSL", "name": "소비자물가(CPI)", "how": "yoy", "unit": "%", "release": "cpi", "rid": 10, "hot": "up",
     "read": "전년 대비 상승률. 예상보다 높으면 금리 인하가 늦어진다는 해석 → 금리↑ 성장주↓가 흔한 반응"},
    {"id": "CPILFESL", "name": "근원 CPI", "how": "yoy", "unit": "%", "release": "cpi", "rid": 10, "hot": "up",
     "read": "식품·에너지를 뺀 물가. 연준이 더 무게를 두는 쪽"},
    {"id": "PCEPILFE", "name": "근원 PCE", "how": "yoy", "unit": "%", "release": "pce", "rid": 54, "hot": "up",
     "read": "연준 물가 목표(2%)의 기준 지표"},
    {"id": "PAYEMS", "name": "비농업 고용", "how": "diff", "unit": "천명", "release": "jobs", "rid": 50, "hot": "up",
     "read": "한 달 새 늘어난 일자리. 너무 강하면 '금리 인하 늦어짐', 너무 약하면 '경기 침체 걱정'"},
    {"id": "UNRATE", "name": "실업률", "how": "level", "unit": "%", "release": "jobs", "rid": 50, "hot": "down",
     "read": "오르면 경기 둔화 신호. 3개월 평균이 1년 최저보다 0.5%p 이상 오르면 '삼의 법칙'(침체 신호)"},
    {"id": "ICSA", "name": "신규 실업수당 청구", "how": "level", "unit": "건", "release": None, "hot": "down",
     "read": "매주 목요일 발표. 고용 둔화를 가장 빨리 보여 줘요"},
    {"id": "RSAFS", "name": "소매판매", "how": "mom", "unit": "%", "release": None, "hot": "up", "read": "미국 소비 체력"},
    {"id": "INDPRO", "name": "산업생산", "how": "yoy", "unit": "%", "release": None, "hot": "up", "read": "제조업 경기"},
    {"id": "A191RL1Q225SBEA", "name": "실질 GDP 성장률", "how": "level", "unit": "%", "release": None, "hot": "up",
     "read": "전 분기 대비 연율"},
    {"id": "DFF", "name": "연방기금금리", "how": "level", "unit": "%", "release": None, "hot": "up", "read": "연준 기준금리(실효)"},
    {"id": "UMCSENT", "name": "미시간 소비자심리", "how": "level", "unit": "", "release": None, "hot": "up",
     "read": "설문(소프트 데이터). 실물(하드 데이터)과 벌어지면 둘 중 하나가 따라가요"},
    {"id": "MORTGAGE30US", "name": "30년 모기지 금리", "how": "level", "unit": "%", "release": None, "hot": "up", "read": "주택시장 부담"},
]
# 지표 발표일 반응을 볼 지수. asia=True면 미국 발표(한국시간 밤) 다음 거래일 등락으로 봐요
REACT = [
    ("^GSPC", "S&P 500", False), ("^IXIC", "나스닥", False), ("^RUT", "러셀 2000", False),
    ("^GDAXI", "독일 DAX", False), ("^KS11", "코스피", True), ("^N225", "닛케이", True), ("^TWII", "대만", True),
    ("^TNX", "미 10년물", False), ("DX-Y.NYB", "달러인덱스", False),
]

TOL = 0.15          # 두 출처 종가 차이 허용(%). 이 안이면 교차확인
RATE_TOL = 0.03     # 금리는 %p 차이 허용
