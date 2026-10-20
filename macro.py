"""계산과 사실 필터. 받아 오기는 sources.py, 목록은 config.py, 화면은 view.py.

- 시세 검증: 야후 종가를 stooq·FRED·네이버 종가와 같은 날짜끼리 맞춰 봐요.
  차이가 config.TOL(0.15%) 안이면 '교차확인', 넘으면 '상충', 두 번째 출처가 없으면 '단일출처'.
- 뉴스: 같은 사건을 서로 다른 언론사 2곳 이상이 보도하면 '교차확인', 한 곳이면 '단일출처'.
  당사자 주장·미확인 보도는 '주장', 전망·추측·질문형 제목은 '의견'.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pandas as pd

import config as C
import sources as S


def all_yahoo() -> list[str]:
    t = [i["yf"] for i in C.INDICES] + [m["yf"] for m in C.MACRO if m["yf"]] + [v["yf"] for v in C.VOL]
    t += [s for s, _ in C.SECTORS] + [s for s, _ in C.THEMES]
    t += [s for v in C.LEADERS.values() for s, _ in v]
    return list(dict.fromkeys(t))


# ─────────────────────────── 시세 ───────────────────────────
def fetch_prices() -> dict[str, pd.DataFrame]:
    """{티커: 일봉}. 한국 대장주는 종목코드, 네이버 지수는 'naver:KOSPI' 키로 들어가요."""
    out = S.yahoo(all_yahoo())
    kr = [c for c, _, _ in C.KR_LEADERS] + [i["naver"] for i in C.INDICES if i.get("naver")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for c, df in zip(kr, pool.map(S.naver, kr)):
            if df is not None and not df.empty:
                out[c if c.isdigit() else "naver:" + c] = df
    return out


def summarize(df: pd.DataFrame | None) -> dict | None:
    """마지막 종가·기준일·1일/5일/20일 변화·50일선 위치."""
    if df is None or len(df) < 2:
        return None
    c = df["close"].astype(float).reset_index(drop=True)
    last = float(c.iloc[-1])

    def back(n):
        return float(c.iloc[-1 - n]) if len(c) > n else None

    def pct(n):
        b = back(n)
        return (last / b - 1) * 100 if b else None

    ma50 = float(c.tail(50).mean()) if len(c) >= 50 else None
    return {
        "last": last, "date": pd.Timestamp(df["date"].iloc[-1]),
        "d1": pct(1), "d5": pct(5), "d20": pct(20),
        "a1": last - back(1) if back(1) is not None else None,          # 금리용 절대 변화(%p)
        "a20": last - back(20) if back(20) is not None else None,
        "ma50": ma50, "above50": (last > ma50) if ma50 else None,
        "spark": c.tail(60).round(4).tolist(),
    }


def verify(primary: dict | None, second: dict | None, src: str = "stooq", tol: float = C.TOL) -> tuple[str, str]:
    """(검증 상태, 설명). 같은 날 종가끼리만 비교해요."""
    if not primary:
        return "없음", "불러오지 못했어요"
    if not second:
        return "단일출처", "두 번째 출처 없음"
    if second["date"].normalize() != primary["date"].normalize():
        return "단일출처", f"{src} 기준일이 달라요({second['date']:%m/%d})"
    gap = abs(second["close"] / primary["last"] - 1) * 100
    return ("교차확인" if gap <= tol else "상충"), f"{src} {second['close']:,.2f} (차이 {gap:.2f}%)"


def stooq_for(sym: str) -> str | None:
    """ETF·미국 종목은 stooq에서 '티커.us'."""
    for i in C.INDICES + C.MACRO:
        if i["yf"] == sym:
            return i.get("stooq")
    if re.fullmatch(r"[A-Z]{1,5}", sym):
        return sym.lower() + ".us"
    if sym == "BRK-B":
        return "brk-b.us"
    return None


def cross_check(syms: list[str]) -> dict[str, dict | None]:
    pairs = [(s, q) for s in syms if (q := stooq_for(s))]
    with ThreadPoolExecutor(max_workers=6) as pool:
        got = list(pool.map(lambda p: S.stooq(p[1]), pairs))
    return {s: g for (s, _), g in zip(pairs, got)}


def fred_summary(df: pd.DataFrame) -> dict | None:
    if df is None or len(df) < 2:
        return None
    v = df["value"].astype(float).reset_index(drop=True)
    last = float(v.iloc[-1])
    return {"last": last, "date": pd.Timestamp(df["date"].iloc[-1]), "a1": last - float(v.iloc[-2]),
            "a20": last - float(v.iloc[-21]) if len(v) > 20 else None, "spark": v.tail(60).round(3).tolist()}


# ─────────────────────────── 뉴스 사실 필터 ───────────────────────────
# 전망·추측·질문형: 사실이 아니라 의견
OPINION = re.compile(
    r"\b(could|might|may|would|should|likely|unlikely|expected to|expects?|forecasts?|predicts?|outlook|"
    r"poised|set to|eyes|bets?|fears?|hopes?|why|what to (?:know|expect|watch)|here'?s|how to|"
    r"stocks? to (?:buy|watch)|top picks?|best|worst|opinion|analysis|commentary|preview)\b|\?$|"
    r"전망|가능성|예상|관측|우려|기대감|분석|칼럼|시각|어디로|될까|할까|주목",
    re.I,
)
# 당사자 주장·미확인 보도
CLAIM = re.compile(
    r"\b(claims?|claimed|allegedly|reportedly|unconfirmed|unverified|rumou?rs?|sources say|according to sources)\b|"
    r"주장|미확인|설\s|소식통|카더라",
    re.I,
)
STOP = set("the a an of to in on for and or at by with from as is are be its it this that after amid over into "
           "new says said stock stocks market markets news today live update updates vs".split())


def _strip_source(title: str, source: str) -> str:
    """구글 뉴스 제목 끝의 ' - 언론사'를 떼요."""
    if source and title.endswith(" - " + source):
        return title[: -len(source) - 3]
    return re.sub(r"\s+-\s+[^-]{2,40}$", "", title)


def parse_rss(text: str, default_source: str = "") -> list[dict]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    out = []
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None and src_el.text else default_source
        pub = it.findtext("pubDate")
        try:
            when = parsedate_to_datetime(pub).astimezone(timezone.utc) if pub else None
        except (TypeError, ValueError):
            when = None
        if not title or not source:
            continue
        out.append({"title": _strip_source(title, source), "source": source, "url": link, "when": when})
    return out


def tokens(title: str) -> set[str]:
    t = re.sub(r"[^\w%.$]+", " ", title.lower())
    return {w for w in t.split() if (len(w) > 2 or any(ch.isdigit() for ch in w)) and w not in STOP}


def classify(title: str) -> str:
    if CLAIM.search(title):
        return "주장"
    if OPINION.search(title):
        return "의견"
    return "사실"


def cluster(items: list[dict], thr: float = 0.34) -> list[dict]:
    """비슷한 제목끼리 묶어 사건 하나로. 서로 다른 언론사 수로 교차확인을 정해요."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    groups: list[dict] = []
    for it in sorted(items, key=lambda x: x["when"] or epoch, reverse=True):
        tk = tokens(it["title"])
        if not tk:
            continue
        best, score = None, 0.0
        for g in groups:
            inter = len(tk & g["tokens"])
            j = inter / len(tk | g["tokens"])
            num = any(any(ch.isdigit() for ch in w) for w in tk & g["tokens"])
            s = j + (0.1 if num and inter >= 3 else 0)
            if s > score:
                best, score = g, s
        if best is not None and score >= thr:
            best["items"].append(it)
            best["sources"].add(it["source"])
            best["tokens"] |= tk
        else:
            groups.append({"items": [it], "sources": {it["source"]}, "tokens": set(tk)})
    out = []
    for g in groups:
        kinds = [classify(i["title"]) for i in g["items"]]
        kind = "주장" if "주장" in kinds else ("사실" if "사실" in kinds else "의견")
        lead = next((i for i, k in zip(g["items"], kinds) if k == kind), g["items"][0])
        status = kind if kind in ("주장", "의견") else ("교차확인" if len(g["sources"]) >= 2 else "단일출처")
        out.append({
            "title": lead["title"], "url": lead["url"], "when": lead["when"], "status": status,
            "sources": sorted(g["sources"]), "n": len(g["sources"]),
            "has_number": bool(re.search(r"\d", lead["title"])),
            "others": [{"title": i["title"], "source": i["source"], "url": i["url"]} for i in g["items"] if i is not lead][:5],
        })
    rank = {"교차확인": 0, "단일출처": 1, "주장": 2, "의견": 3}
    out.sort(key=lambda x: (rank[x["status"]], -x["n"], not x["has_number"], -(x["when"] or epoch).timestamp()))
    return out


def _google_rss(lang: str, q: str) -> list[dict]:
    hl = {"en": ("en-US", "US", "US:en"), "ko": ("ko", "KR", "KR:ko")}[lang]
    text = S.get_text("https://news.google.com/rss/search",
                      {"q": q + " when:1d", "hl": hl[0], "gl": hl[1], "ceid": hl[2]})
    return parse_rss(text) if text else []


def _direct(name: str, url: str) -> list[dict]:
    text = S.get_text(url)
    return parse_rss(text, default_source=name) if text else []


MOCK_NEWS = [
    ("S&P 500 rises 0.4% as chip stocks rebound", "Reuters"),
    ("S&P 500 gains 0.4% as chipmakers rebound", "AP News"),
    ("Oil could hit $120 if Hormuz stays closed, analysts say", "CNBC"),
    ("Houthis claim attack on Saudi Aramco facility", "Reuters"),
    ("코스피 1.76% 오른 5,768 마감…기관 순매수", "연합뉴스"),
]


def fetch_news() -> list[dict]:
    if S.MOCK:
        now = datetime.now(timezone.utc)
        return cluster([{"title": t, "source": s, "url": f"https://example.com/{i}", "when": now}
                        for i, (t, s) in enumerate(MOCK_NEWS)])
    jobs = [lambda l=l, q=q: _google_rss(l, q) for l, q in C.NEWS_QUERIES]
    jobs += [lambda n=n, u=u: _direct(n, u) for n, u in C.DIRECT_FEEDS]
    with ThreadPoolExecutor(max_workers=6) as pool:
        lists = list(pool.map(lambda f: f(), jobs))
    seen, items = set(), []
    for lst in lists:
        for it in lst:
            key = (it["source"], it["title"].lower())
            if key not in seen:
                seen.add(key)
                items.append(it)
    return cluster(items)


# ─────────────────────────── 한 번에 모으기 ───────────────────────────
def snapshot() -> dict:
    """화면·브리핑이 함께 쓰는 묶음."""
    prices = fetch_prices()
    sm = {t: summarize(df) for t, df in prices.items()}
    check = [i["yf"] for i in C.INDICES if i.get("stooq")] + [m["yf"] for m in C.MACRO if m.get("stooq")]
    check += [s for s, _ in C.SECTORS] + [s for s, _ in C.THEMES] + [s for v in C.LEADERS.values() for s, _ in v]
    second = cross_check(check)
    ver = {s: verify(sm.get(s), second.get(s)) for s in sm}
    # 한국 지수: 야후와 네이버 종가를 맞춰 봐요
    for i in C.INDICES:
        if i.get("naver"):
            nv = sm.get("naver:" + i["naver"])
            ver[i["yf"]] = verify(sm.get(i["yf"]), nv and {"date": nv["date"], "close": nv["last"]}, "네이버")
            if not sm.get(i["yf"]) and nv:
                sm[i["yf"]] = nv
                ver[i["yf"]] = ("단일출처", "네이버")
    ids = [f["id"] for f in C.FRED] + [m["fred"] for m in C.MACRO if m.get("fred")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        fred = {k: fred_summary(v) for k, v in zip(ids, pool.map(S.fred, ids))}
    # 금리는 야후(^TNX 등)와 FRED를 맞춰 봐요. 야후 티커가 없으면 FRED만
    for m in C.MACRO:
        if not m.get("fred"):
            continue
        key = m["yf"] or "fred:" + m["fred"]
        a, b = sm.get(m["yf"]) if m["yf"] else None, fred.get(m["fred"])
        if a and b:
            same = a["date"].normalize() == b["date"].normalize()
            gap = abs(a["last"] - b["last"])
            ver[key] = (("교차확인" if gap <= C.RATE_TOL else "상충") if same else "단일출처",
                        f"FRED {b['last']:.3f}% ({b['date']:%m/%d})")
        elif b:
            sm[key] = {**b, "d1": None, "d5": None, "d20": None, "above50": None, "ma50": None}
            ver[key] = ("단일출처", "FRED")
    return {"at": S.now_kst(), "sm": sm, "ver": ver, "fred": fred, "news": fetch_news()}


def key_of(m: dict) -> str:
    """MACRO 항목이 snapshot['sm']에 들어간 키."""
    return m["yf"] or "fred:" + m["fred"]


def facts(snap: dict) -> list[str]:
    """숫자끼리 비교만 해서 만든 한 줄 요약(전망 없음)."""
    sm, out = snap["sm"], []
    spx, rsp, spy = sm.get("^GSPC"), sm.get("RSP"), sm.get("SPY")
    if spx and spx["d1"] is not None:
        out.append(f"S&P 500 {spx['d1']:+.2f}%")
    ks = sm.get("^KS11")
    if ks and ks["d1"] is not None:
        out.append(f"코스피 {ks['d1']:+.2f}%")
    if rsp and spy and rsp["d1"] is not None and spy["d1"] is not None:
        gap = rsp["d1"] - spy["d1"]
        if abs(gap) >= 0.3:
            out.append(f"동일가중(RSP) {rsp['d1']:+.2f}% → " + ("시총가중보다 약함(소수 대형주 쏠림)" if gap < 0 else "시총가중보다 강함(중소형주까지 확산)"))
    secs = [(n, sm[s]["d1"]) for s, n in C.SECTORS if sm.get(s) and sm[s]["d1"] is not None]
    if secs:
        secs.sort(key=lambda x: x[1])
        up = sum(1 for _, v in secs if v > 0)
        out.append(f"섹터 {up}/{len(secs)}개 상승 · 최강 {secs[-1][0]} {secs[-1][1]:+.1f}% · 최약 {secs[0][0]} {secs[0][1]:+.1f}%")
    above = [sm[s]["above50"] for s, _ in C.SECTORS if sm.get(s) and sm[s]["above50"] is not None]
    if above:
        out.append(f"50일선 위 섹터 {sum(above)}/{len(above)}")
    vix, hy = sm.get("^VIX"), snap["fred"].get("BAMLH0A0HYM2")
    if vix:
        out.append(f"VIX {vix['last']:.1f}")
    if hy and hy.get("a20") is not None:
        out.append(f"하이일드 스프레드 {hy['last']:.2f}% (20일 {hy['a20']:+.2f}%p)")
    return out
