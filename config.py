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
    ("TAN", "태양광"), ("FAN", "풍력"), ("RSP", "S&P 동일가중"), ("SPY", "S&P 500"),
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
DIRECT_FEEDS = [("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html")]

TOL = 0.15          # 두 출처 종가 차이 허용(%). 이 안이면 교차확인
RATE_TOL = 0.03     # 금리는 %p 차이 허용
