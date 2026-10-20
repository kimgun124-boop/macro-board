"""코스피·코스닥 수급(투자자별 순매수)과 시장 요약. 밸류체인 신고가 보드(very)의 data.py 방식을 그대로 옮겼어요.

- 시장 요약: stock.naver.com / m.stock.naver.com 지수 basic·integration (상승·하락 종목 수, 당일 개인·외국인·기관, 프로그램)
- 일별 수급: stock.naver.com 시장 투자자별 매매동향 → 안 되면 예전 finance.naver.com 표
금액은 억원.
"""
from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

import sources as S

STOCK_API = "https://stock.naver.com/api"
M_API = "https://m.stock.naver.com/api"
INDEX_POLLING_URL = "https://polling.finance.naver.com/api/realtime/domestic/index"
INVESTOR_URL = "https://finance.naver.com/sise/investorDealTrendDay.naver"
JSON_HEADERS = {"Accept": "application/json", "Referer": "https://stock.naver.com/"}
MARKETS = {"코스피": "KOSPI", "코스닥": "KOSDAQ"}
INVESTOR_MARKETS = {"코스피": "01", "코스닥": "02"}
INVESTORS = ["개인", "외국인", "기관"]
INST_DETAIL = ["금융투자", "보험", "투신(사모)", "은행", "기타금융", "연기금", "기타법인"]
_GUBUN = {"1000": "금융투자", "2000": "보험", "3000": "투신(사모)", "3100": "투신(사모)", "4000": "은행",
          "5000": "기타금융", "6000": "연기금", "7000": "기타법인", "7100": "기타법인",
          "8000": "개인", "9000": "외국인", "9001": "외국인"}


def to_num(text) -> float | None:
    try:
        return float(str(text).replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _num(v) -> float | None:
    """'+2,746,972' / '-4,822' / '1,234억' 같은 네이버 문자열 숫자 → float."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"[+-]?[\d,]*\.?\d+", str(v))
    return to_num(m.group(0)) if m else None


def _strip_tags(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t).replace("&nbsp;", " ").strip()


def _get_json(urls, params=None, timeout: int = 8):
    """주소 여러 개를 차례로 시도해 처음 성공한 JSON을 돌려줘요. 모두 실패하면 None."""
    for url in urls:
        try:
            r = S.session.get(url, params=params, headers=JSON_HEADERS, timeout=timeout)
            if r.status_code != 200:
                continue
            return r.json()
        except (requests.RequestException, ValueError):
            continue
    return None


# ─────────────────────────── 코스피·코스닥 요약 ───────────────────────────
def parse_index_overview(basic: dict | None, integ: dict | None, polling: dict | None = None) -> dict:
    basic = basic or {}
    integ = integ or {}
    pol = ((polling or {}).get("datas") or [{}])[0] if polling else {}
    last = _num(basic.get("closePrice")) or _num(pol.get("closePrice"))
    diff = _num(basic.get("compareToPreviousClosePrice"))
    if diff is None:
        diff = _num(pol.get("compareToPreviousClosePrice"))
    rate = _num(basic.get("fluctuationsRatio"))
    if rate is None:
        rate = _num(pol.get("fluctuationsRatio"))
    direction = ((basic.get("compareToPreviousPrice") or pol.get("compareToPreviousPrice") or {}).get("name") or "")
    if diff is not None and direction == "FALLING" and diff > 0:
        diff, rate = -diff, -abs(rate or 0)
    ud = integ.get("upDownStockInfo") or {}
    breadth = {k: _num(ud.get(f)) for k, f in (("상한", "upperCount"), ("상승", "riseCount"), ("보합", "steadyCount"),
                                                ("하락", "fallCount"), ("하한", "lowerCount"))}
    if all(v is None for v in breadth.values()):
        breadth = None
    dt = integ.get("dealTrendInfo") or {}
    deal = {"개인": _num(dt.get("personalValue")), "외국인": _num(dt.get("foreignValue")),
            "기관": _num(dt.get("institutionalValue")), "bizdate": dt.get("bizdate")}
    if all(deal[k] is None for k in INVESTORS):
        deal = None
    elif max(abs(deal[k] or 0) for k in INVESTORS) > 5e6:     # 백만원 단위로 오면 억원으로
        deal.update({k: (deal[k] / 100 if deal[k] is not None else None) for k in INVESTORS})
    pt = integ.get("programTrendInfo") or {}
    return {"last": last, "diff": diff, "rate": rate, "time": basic.get("localTradedAt") or pol.get("localTradedAt"),
            "breadth": breadth, "deal": deal, "program": _num(pt.get("indexTotalReal")),
            "status": basic.get("marketStatus") or pol.get("marketStatus")}


def _rng(seed: str) -> random.Random:
    return random.Random(seed)


def fetch_market_overview() -> dict[str, dict]:
    """{'코스피': {...}, '코스닥': {...}} — 지수, 상승·하락 종목 수, 당일 투자자별 순매수(억원), 프로그램."""
    if S.MOCK:
        out = {}
        for name, code in MARKETS.items():
            rng = _rng(code)
            total = 930 if code == "KOSPI" else 1770
            rise, steady = rng.randint(int(total * .25), int(total * .6)), rng.randint(40, 90)
            f, i = rng.randint(-8000, 8000), rng.randint(-6000, 6000)
            out[name] = {"last": 3100.0 if code == "KOSPI" else 850.0, "diff": 5.0, "rate": 0.2, "time": None,
                         "breadth": {"상한": 1, "상승": rise, "보합": steady, "하락": total - rise - steady, "하한": 0},
                         "deal": {"개인": -(f + i), "외국인": f, "기관": i, "bizdate": S.now_kst().strftime("%Y%m%d")},
                         "program": rng.randint(-3000, 3000), "status": "CLOSE"}
        return out

    def one(item):
        name, code = item
        basic = _get_json([f"{STOCK_API}/securityFe/api/index/{code}/basic", f"{M_API}/index/{code}/basic"])
        integ = _get_json([f"{STOCK_API}/securityFe/api/index/{code}/integration", f"{M_API}/index/{code}/integration"])
        polling = None
        if not basic or basic.get("closePrice") is None:
            polling = _get_json([f"{INDEX_POLLING_URL}/{code}"])
        return name, parse_index_overview(basic, integ, polling)

    with ThreadPoolExecutor(max_workers=2) as pool:
        out = dict(pool.map(one, MARKETS.items()))
    ok = any(v.get("last") for v in out.values())
    S.mark("네이버 시장 요약", ok, "" if ok else "응답 없음")
    return out


# ─────────────────────────── 일별 투자자별 순매수 ───────────────────────────
def parse_market_trend(payload) -> pd.DataFrame:
    content = (payload or {}).get("content") if isinstance(payload, dict) else payload
    rows = []
    for c in content or []:
        bd = str(c.get("bizdate") or "")
        if not re.fullmatch(r"\d{8}", bd):
            continue
        row = {"date": pd.Timestamp(int(bd[:4]), int(bd[4:6]), int(bd[6:]))}
        for k in ["개인", "외국인"] + INST_DETAIL:
            row[k] = 0.0
        seen = False
        for a in c.get("netAmounts") or []:
            key = _GUBUN.get(str(a.get("investorGubun")))
            v = _num(a.get("diffValue"))
            if key and v is not None:
                row[key] += v
                seen = True
        if seen:
            row["기관"] = sum(row[k] for k in INST_DETAIL if k != "기타법인")
            rows.append(row)
    cols = ["date"] + INVESTORS + INST_DETAIL
    return pd.DataFrame(rows, columns=cols).sort_values("date").drop_duplicates("date").reset_index(drop=True)


def _scale_to_eok(df: pd.DataFrame, ref: dict | None) -> pd.DataFrame:
    """API 금액 단위를 억원으로 맞춰요(당일 요약 순매수가 있으면 그걸로, 없으면 크기로 짐작)."""
    if df.empty:
        return df
    cols = INVESTORS + INST_DETAIL
    div = None
    if ref and ref.get("bizdate"):
        hit = df[df["date"] == pd.to_datetime(str(ref["bizdate"]), format="%Y%m%d", errors="coerce")]
        if not hit.empty:
            ratios = [abs(hit.iloc[0][k] / ref[k]) for k in INVESTORS if ref.get(k) and hit.iloc[0][k]]
            if ratios:
                r = sorted(ratios)[len(ratios) // 2]
                div = min((1, 100, 1e8), key=lambda d: abs((r / d) - 1) if r else 9e9)
    if div is None:
        med = max(df[k].abs().median() for k in INVESTORS)
        div = 1e8 if med > 1e9 else (100 if med > 5e4 else 1)
    out = df.copy()
    out[cols] = out[cols] / div
    return out


def parse_investor_trend(text: str) -> list[dict]:
    """(예전) 네이버 투자자별 매매동향 HTML(일별, 억원) → [{date, 개인, 외국인, 기관}, ...]"""
    header = [_strip_tags(h).replace(" ", "") for h in re.findall(r"<th[^>]*>(.*?)</th>", text, re.S)]

    def col(name, default):
        for i, h in enumerate(header):
            if h.startswith(name):
                return i
        return default

    idx = {"개인": col("개인", 1), "외국인": col("외국인", 2), "기관": col("기관", 3)}
    rows = []
    for tr in re.split(r"<tr[\s>]", text):
        tds = [_strip_tags(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not tds:
            continue
        m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", tds[0].strip())
        if not m:
            continue
        row = {"date": pd.Timestamp(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))}
        for name, i in idx.items():
            row[name] = to_num(tds[i]) if i < len(tds) else None
        if all(row[n] is not None for n in INVESTORS):
            rows.append(row)
    return rows


def fetch_investor_flows(overview: dict | None = None) -> dict[str, pd.DataFrame]:
    """코스피·코스닥 일별 투자자별 순매수(억원): 개인·외국인·기관 + 기관 세부."""
    cols = ["date"] + INVESTORS + INST_DETAIL
    out = {}
    for market, code in MARKETS.items():
        if S.MOCK:
            rng = _rng(market)
            rows = []
            for dt in pd.bdate_range(end=S.now_kst().date(), periods=20):
                det = {k: float(rng.randint(-2500, 2500)) for k in INST_DETAIL}
                inst = sum(v for k, v in det.items() if k != "기타법인")
                f = float(rng.randint(-8000, 8000))
                rows.append({"date": dt, "개인": -(f + inst + det["기타법인"]), "외국인": f, "기관": inst, **det})
            out[market] = pd.DataFrame(rows, columns=cols)
            continue
        payload = _get_json([f"{STOCK_API}/domestic/market/trend/daily"],
                            params={"tradeType": "KRX", "marketType": code, "bizdate": S.now_kst().strftime("%Y%m%d"),
                                    "startIdx": 0, "pageSize": 30})
        df = parse_market_trend(payload)
        if not df.empty:
            out[market] = _scale_to_eok(df, ((overview or {}).get(market) or {}).get("deal"))
            continue
        rows = []
        for page in (1, 2):
            try:
                r = S.session.get(INVESTOR_URL, params={"bizdate": S.now_kst().strftime("%Y%m%d"),
                                                        "sosok": INVESTOR_MARKETS[market], "page": page}, timeout=8)
                r.raise_for_status()
                try:
                    text = r.content.decode("utf-8")
                except UnicodeDecodeError:
                    text = r.content.decode("cp949", errors="replace")
                rows += parse_investor_trend(text)
            except requests.RequestException:
                break
        df = pd.DataFrame(rows, columns=["date"] + INVESTORS)
        for k in INST_DETAIL:
            df[k] = float("nan")
        out[market] = df[cols].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    ok = any(not v.empty for v in out.values())
    S.mark("네이버 투자자별 수급", ok, "" if ok else "응답 없음")
    return out
