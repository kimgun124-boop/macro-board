"""뉴스 요약(규칙 기반, 추가 요금 없음). 새 뉴스가 들어올 때마다(15분 캐시) 다시 계산돼요.

- 주제 나누기: 제목의 단어로 이란·호르무즈 / 사우디·후티 / 유가 / 연준·금리 / 반도체·AI / 한국 증시 … 로 묶어요.
- 핵심 뉴스: 같은 사건을 보도한 언론사 수(많을수록 큰 뉴스) + 주요 외신 수 + 최신순으로 골라요.
- 영어 제목은 핵심 단어를 한국어로 바꿔 붙여요(번역이 아니라 단어 바꾸기).
- 주제마다 관련 지표(유가·금리·반도체 ETF 등)가 실제로 어떻게 움직였는지 숫자를 같이 보여 줘요.
Claude가 쓴 해석 글(reports/)의 '## 뉴스 해석'은 화면이 따로 맨 위에 보여 줘요.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import issues

# (키, 한국어 이름, 제목에서 찾는 단어, 시장으로 이어지는 길, 같이 볼 지표) — 위에서부터 먼저 맞는 주제로 들어가요
TOPICS = [
    ("iran", "이란·호르무즈", r"iran|hormuz|kharg|tehran|araqchi|irgc|이란|호르무즈",
     "원유 공급 위협 → 유가↑ → 에너지↑ · 항공·화학↓ · 물가·금리↑", ("CL=F", "^OVX")),
    ("saudi", "사우디·후티·홍해", r"saudi|houthi|aramco|yemen|riyadh|red sea|사우디|후티|홍해|예멘",
     "사우디 본토·수출 위험 → 브렌트↑ · 걸프 투자·인프라 수주 지연", ("BZ=F", "XLE")),
    ("israel", "이스라엘·레바논·가자", r"israel|gaza|west bank|hezbollah|lebanon|이스라엘|가자|레바논|헤즈볼라",
     "직접 원유 공급과 멀어 시장 영향은 보통 작아요", ("ITA",)),
    ("russia", "러시아·우크라이나", r"russia|ukrain|kremlin|putin|zelensk|nato|러시아|우크라이나|나토",
     "유럽 가스·방산 → 방산↑", ("ITA",)),
    ("oil", "유가·원자재", r"\boil\b|crude|brent|\bwti\b|opec|barrel|\bgold\b|copper|유가|원유|금값|구리|원자재",
     "유가 → 물가 → 금리", ("CL=F", "GC=F")),
    ("fed", "연준·금리", r"\bfed\b|fomc|powell|rate cut|rate hike|treasur|yields?|bond|연준|금리|국채|파월|기준금리",
     "금리↑ → 성장주·부동산 부담 / 금리↓ → 성장주·소형주 유리", ("^TNX", "fred:DGS2")),
    ("macro", "물가·고용·경기", r"inflation|\bcpi\b|\bpce\b|jobs|payroll|unemploy|gdp|recession|retail sales|물가|고용|실업|경기|소비",
     "물가↑ → 금리 인하 기대↓ / 고용↓ → 경기 우려", ("^TNX",)),
    ("chips", "반도체·AI", r"nvidia|chip|semiconductor|\bai\b|hbm|memory|tsmc|hynix|micron|data ?center|openai|반도체|하이닉스|삼성전자|HBM|AI|메모리|엔비디아",
     "AI 투자 → 반도체·전력기기 / AI 의심 → 반도체 매도", ("SMH", "000660")),
    ("kr", "한국 증시", r"kospi|kosdaq|korea|코스피|코스닥|외국인|기관|증시|개미|공매도|밸류업",
     "외국인 수급 → 코스피 방향", ("^KS11", "^KQ11")),
    ("fx", "환율·달러", r"dollar|\byen\b|currency|환율|원[/·]?달러|달러|엔화",
     "원화 약세 → 외국인 매도 부담", ("KRW=X", "DX-Y.NYB")),
    ("trade", "무역·관세·중국", r"tariff|\btrade\b|trade war|china|beijing|\bxi\b|export|관세|무역|중국|수출",
     "관세·수출 → 수출주·신흥국", ("EEM", "EWY")),
    ("earn", "기업·실적", r"earnings|profit|revenue|guidance|quarter|results|실적|영업이익|매출|분기",
     "실적 → 개별 종목·섹터", ("SPY",)),
    ("us", "미국 증시", r"stocks?|s&p|nasdaq|\bdow\b|wall street|뉴욕증시|미국 증시|월가",
     "미국 지수 → 다음 날 한국", ("^GSPC", "^IXIC")),
]
GEO_KEYS = ("iran", "saudi", "israel", "russia", "oil")
NAMES = {k: n for k, n, *_ in TOPICS} | {"etc": "기타"}

# 영어 제목 → 한국어 핵심어(순서대로, 중복 없이)
TERMS = [
    (r"strait of hormuz|hormuz", "호르무즈"), (r"\biran(?:'s|ian)?\b", "이란"), (r"kharg", "하르그섬"),
    (r"araqchi", "아락치 외무장관"), (r"\birgc\b|revolutionary guard", "혁명수비대"),
    (r"saudi", "사우디"), (r"houthi", "후티"), (r"aramco", "아람코"), (r"red sea", "홍해"),
    (r"israel", "이스라엘"), (r"west bank", "요르단강 서안"), (r"gaza", "가자"), (r"hezbollah", "헤즈볼라"),
    (r"russia", "러시아"), (r"ukrain", "우크라이나"), (r"china|beijing", "중국"), (r"japan", "일본"),
    (r"canada", "캐나다"), (r"europe|\beu\b|ecb", "유럽"), (r"\b(?:us|u\.s\.|american|washington)\b", "미국"),
    (r"trump", "트럼프"), (r"\bfed\b|federal reserve|fomc", "연준"), (r"powell", "파월"),
    (r"rate cuts?", "금리 인하"), (r"rate hikes?", "금리 인상"), (r"treasur|yields?|bonds?", "국채금리"),
    (r"inflation|\bcpi\b|consumer prices", "물가"), (r"jobs|payroll|unemploy", "고용"), (r"recession", "경기침체"),
    (r"brent", "브렌트유"), (r"\bwti\b", "WTI"), (r"\boil\b|crude", "유가"), (r"opec", "OPEC"), (r"\bgold\b", "금"),
    (r"nvidia", "엔비디아"), (r"semiconductor|chips?\b|chipmakers?", "반도체"), (r"memory|hbm|dram", "메모리"),
    (r"\bai\b|artificial intelligence", "AI"), (r"data ?cent", "데이터센터"), (r"tsmc", "TSMC"),
    (r"s&p 500|s&p", "S&P500"), (r"nasdaq", "나스닥"), (r"\bdow\b", "다우"), (r"stocks?|shares|equities", "주식"),
    (r"dollar", "달러"), (r"\byen\b", "엔화"), (r"tariffs?", "관세"), (r"earnings|profit|results", "실적"),
    (r"terminals?", "수출 터미널"), (r"tankers?", "유조선"), (r"\bmines?\b", "기뢰"), (r"blockade", "봉쇄"),
    (r"(\w+)-month high", r"\1개월 고점"), (r"record high|all-time high|record", "사상 최고"),
    (r"(\w+)-month low", r"\1개월 저점"), (r"investment event|\bfii\b|conference|forum", "투자 행사"),
    (r"attacks?|strikes?", "공격"), (r"threats?", "위협"), (r"ceasefire|truce", "휴전"), (r"talks|negotiat", "협상"),
    (r"sanction", "제재"), (r"seiz", "나포"), (r"missile|drone", "미사일·드론"),
    (r"postpone|delay", "연기"), (r"cancel", "취소"), (r"detain|arrest", "구금"), (r"blame", "책임 돌림"),
    (r"\bempty\b|\bhalt|\bstall", "멈춤"), (r"rall(?:y|ies)|soar|surges?|jumps?", "급등"),
    (r"ticks? up|\brises?\b|\bclimbs?\b|\bgains?\b|\bhigher\b", "상승"), (r"plunge|tumbles?|sink|slumps?", "급락"),
    (r"\bfalls?\b|\bdrops?\b|\bslides?\b|\blower\b|\bdeclines?\b", "하락"), (r"\bholds?\b|\bsteady\b|\bflat\b", "유지"), (r"waver|mixed", "등락"),
    (r"flows?", "물동량"), (r"settler", "정착민"), (r"violen", "폭력"), (r"warns?", "경고"),
]
WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
         "nine": "9", "ten": "10", "eleven": "11", "twelve": "12"}
HANGUL = re.compile(r"[가-힣]")
FACT = ("교차확인", "단일출처")
EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def gist(title: str) -> list[str]:
    """영어 제목의 핵심어를 한국어로. 한국어 제목이면 빈 목록."""
    if HANGUL.search(title):
        return []
    out = []
    for rx, ko in TERMS:
        m = re.search(rx, title, re.I)
        if not m:
            continue
        word = ko
        if "\\1" in ko:
            n = m.group(1).lower()
            word = ko.replace("\\1", WORDS.get(n, n))
        if word not in out:
            out.append(word)
    return out[:7]


def topic_of(title: str) -> str:
    for key, _, rx, *_ in TOPICS:
        if re.search(rx, title, re.I):
            return key
    return "etc"


def weight(n: dict, now: datetime) -> float:
    """큰 뉴스 점수: 보도한 언론사 수 + 주요 외신 + 최근일수록 가산."""
    age = (now - (n.get("when") or EPOCH)).total_seconds() / 3600
    fresh = 3 if age <= 3 else 1.5 if age <= 8 else 0
    return n.get("n", 1) + 2 * len(n.get("major", [])) + fresh


def build(snap: dict, only: tuple[str, ...] | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    news = []
    for n in snap.get("news") or []:
        k = topic_of(n["title"])
        if only and k not in only:
            continue
        news.append({**n, "topic": k, "w": weight(n, now), "ko": gist(n["title"])})
    facts = [n for n in news if n["status"] in FACT]
    top = sorted(facts, key=lambda n: -n["w"])[:5]
    new = sorted([n for n in facts if n.get("when") and now - n["when"] <= timedelta(hours=3) and n.get("n", 1) >= 2],
                 key=lambda n: -n["w"])[:3]
    topics = []
    for key, name, _, path, drivers in TOPICS + [("etc", "기타", "", "", ())]:
        hit = sorted([n for n in news if n["topic"] == key], key=lambda n: -n["w"])
        if not hit:
            continue
        topics.append({"key": key, "name": name, "path": path, "news": hit, "n": len(hit),
                       "n_cross": sum(1 for n in hit if n["status"] == "교차확인"),
                       "moves": [(issues.name_of(d) if not d.isdigit() else "SK하이닉스" if d == "000660" else d,
                                  issues.move(snap, d)[1]) for d in drivers]})
    topics.sort(key=lambda t: -(t["n_cross"] * 2 + t["n"]))
    return {"news": news, "top": top, "new": new, "topics": topics, "lines": read(snap, news) if only else []}


def read(snap: dict, news: list[dict]) -> list[str]:
    """전쟁·유가 뉴스와 숫자를 맞춰 본 한 줄 해석(규칙)."""
    m = {s: issues.move(snap, s)[0] for s in ("CL=F", "^TNX", "XLE", "SPY", "JETS")}
    oil, ten = m["CL=F"], m["^TNX"]
    out = []
    n, cross = len(news), sum(1 for x in news if x["status"] == "교차확인")
    if n:
        out.append(f"지난 24시간 전쟁·지정학·유가 뉴스 {n}건, 그중 두 곳 이상이 같이 보도한 것 {cross}건.")
    if oil is not None:
        if oil >= 3 and n >= 3:
            out.append(f"뉴스와 유가가 같은 방향이에요(WTI 5일 {oil:+.1f}%). 지정학 위험이 가격에 붙는 중.")
        elif oil <= -3 and n >= 3:
            out.append(f"뉴스는 많은데 유가는 내려요(WTI 5일 {oil:+.1f}%). 시장이 위험에 익숙해졌거나 공급이 버티는 중.")
        else:
            out.append(f"유가는 큰 방향 없이 버텨요(WTI 5일 {oil:+.1f}%). 위협과 실제 물동량이 맞서는 구간.")
    if oil is not None and ten is not None:
        if oil > 0 and ten > 0:
            out.append(f"유가와 미 10년물이 같이 올라요(10년물 5일 {ten:+.2f}%p). 유가 → 물가 → 금리 경로가 작동 중, 주식엔 부담.")
        elif oil > 0 >= ten:
            out.append(f"유가는 오르는데 금리는 안정적이에요(10년물 5일 {ten:+.2f}%p). 블로그 관점: 시장의 면역력이 높아진 상태.")
    if m["XLE"] is not None and m["SPY"] is not None:
        rel = m["XLE"] - m["SPY"]
        out.append(f"에너지(XLE)가 S&P보다 5일 {rel:+.1f}%p" + (f", 항공(JETS) {m['JETS']:+.1f}%" if m["JETS"] is not None else "")
                   + (" → 섹터도 유가 쪽으로 기울었어요." if rel > 0 else " → 섹터 반응은 아직 약해요."))
    return out
