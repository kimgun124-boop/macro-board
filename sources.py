"""바깥 사이트에서 데이터를 받아 오는 곳. 화면이나 계산은 여기 없어요.

- 야후(yfinance): 지수·ETF·종목·환율·원자재 일봉(15분 안팎 지연)
- stooq: 두 번째 출처 종가
- FRED: 미국 금리·스프레드
- 네이버: 한국 종목·지수 일봉
- 구글 뉴스·CNBC RSS: 뉴스 제목

MACRO_MOCK=1 로 실행하면 인터넷 없이 가짜 데이터로 화면을 확인할 수 있어요.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

KST = timezone(timedelta(hours=9))
MOCK = os.environ.get("MACRO_MOCK") == "1"
COLUMNS = ["date", "open", "high", "low", "close", "volume"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}


class _GuardedSession(requests.Session):
    """한 사이트에서 연결 실패가 연달아 6번 나면 60초 동안은 바로 실패로 돌려요(앱이 멈추지 않게)."""
    FAIL_LIMIT, COOL = 6, 60.0

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._fails: dict[str, list] = {}

    def request(self, method, url, *args, **kwargs):
        host = requests.utils.urlparse(url).hostname or ""
        with self._lock:
            n, since = self._fails.get(host, [0, 0.0])
            if n >= self.FAIL_LIMIT and time.time() - since < self.COOL:
                raise requests.ConnectionError(f"{host} 연결이 계속 실패해 잠시 쉬는 중이에요")
        kwargs.setdefault("timeout", 10)
        try:
            r = super().request(method, url, *args, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            with self._lock:
                self._fails[host] = [self._fails.get(host, [0, 0.0])[0] + 1, time.time()]
            raise
        with self._lock:
            self._fails.pop(host, None)
        return r


session = _GuardedSession()
session.headers.update(HEADERS)


# 출처별 마지막 상태(화면 아래 '데이터 상태'에 보여 줘요). {이름: (성공, 설명, 시각)}
STATUS: dict[str, tuple[bool, str, str]] = {}


def mark(name: str, ok: bool, msg: str = "") -> None:
    STATUS[name] = (ok, msg, datetime.now(KST).strftime("%H:%M:%S"))


def now_kst() -> datetime:
    return datetime.now(KST)


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def day(x):
    """날짜를 '시간대 없음 · 나노초(ns) 단위 · 자정'으로 맞춰요.
    출처마다 단위가 달라(야후 ns, 네이버·CSV us) 날짜를 맞춰 붙이는 merge_asof가 MergeError로 멈추는 걸 막아요."""
    d = pd.to_datetime(x, errors="coerce")
    if isinstance(d, pd.Series):
        if d.dt.tz is not None:
            d = d.dt.tz_localize(None)
        return d.dt.normalize().astype("datetime64[ns]")
    d = pd.DatetimeIndex(d)
    if d.tz is not None:
        d = d.tz_localize(None)
    return d.normalize().as_unit("ns")


# ─────────────────────────── 가짜 데이터(MACRO_MOCK=1) ───────────────────────────
# 연습용 가짜 시세의 시작값(금리·VIX·유가·환율은 실제와 비슷한 크기로)
MOCK_BASE = {"^TNX": 4.6, "^FVX": 4.3, "^TYX": 4.9, "^VIX": 19.0, "CL=F": 90.0, "BZ=F": 95.0, "KRW=X": 1390.0,
             "^IXIC": 26000.0, "^GSPC": 7600.0, "^KS11": 5700.0, "^KQ11": 800.0, "KOSPI": 5700.0, "KOSDAQ": 800.0}
MOCK_VOL = {"^TNX": 0.008, "^FVX": 0.008, "^TYX": 0.008, "KRW=X": 0.003, "^VIX": 0.04}


def mock_history(code: str, count: int = 300) -> pd.DataFrame:
    rng = random.Random(int(hashlib.md5(code.encode()).hexdigest()[:8], 16))
    dates = pd.bdate_range(end=now_kst().date(), periods=count)
    price, drift, rows = MOCK_BASE.get(code) or rng.uniform(20, 5_000), rng.uniform(-0.001, 0.002), []
    if code in MOCK_VOL:
        drift = 0.0
    for _ in dates:
        o = price
        price = max(1.0, price * (1 + rng.gauss(drift, MOCK_VOL.get(code, 0.015))))
        hi, lo = max(o, price) * (1 + abs(rng.gauss(0, .006))), min(o, price) * (1 - abs(rng.gauss(0, .006)))
        rows.append((round(o, 2), round(hi, 2), round(lo, 2), round(price, 2), int(rng.uniform(1e5, 1e7))))
    df = pd.DataFrame(rows, columns=COLUMNS[1:])
    df.insert(0, "date", day(dates))
    return df


# ─────────────────────────── 야후 ───────────────────────────
def normalize_yf(hist: pd.DataFrame) -> pd.DataFrame:
    """yfinance 결과 → date, open, high, low, close, volume."""
    if hist is None or hist.empty or "Close" not in hist:
        return empty()
    idx = day(hist.index)

    def col(name):
        if name not in hist:
            return None
        v = hist[name]
        if isinstance(v, pd.DataFrame):
            v = v.iloc[:, 0]
        return pd.to_numeric(v, errors="coerce").values

    close = col("Close")
    df = pd.DataFrame({"date": idx, "close": close})
    for k in ("open", "high", "low"):
        v = col(k.capitalize())
        df[k] = close if v is None else v
    v = col("Volume")
    df["volume"] = 0 if v is None else v
    df = df[COLUMNS].dropna(subset=["close"])
    df[["open", "high", "low"]] = df[["open", "high", "low"]].apply(lambda x: x.fillna(df["close"]))
    df["volume"] = df["volume"].fillna(0)
    df = df[df["close"] > 0]
    return df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def yahoo(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """여러 티커를 한 번에. 못 받은 티커는 결과에서 빠져요."""
    if MOCK:
        n = {"10y": 2600, "5y": 1300}.get(period, 300)
        return {t: mock_history(t, n) for t in tickers}
    try:
        import yfinance as yf
    except ImportError:
        return {}
    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(tickers), 60):
        part = tickers[i:i + 60]
        try:
            raw = yf.download(part, period=period, interval="1d", group_by="ticker", auto_adjust=False,
                              threads=True, progress=False)
        except Exception:
            raw = None
        if raw is None or raw.empty:
            continue
        for t in part:
            if isinstance(raw.columns, pd.MultiIndex):
                if t not in raw.columns.get_level_values(0):
                    continue
                sub = raw[t]
            elif len(part) == 1:
                sub = raw
            else:
                continue
            df = normalize_yf(sub)
            if not df.empty:
                out[t] = df
    _mt_prune()
    # 한꺼번에 받다 빠진 티커는 하나씩 다시(너무 많이 빠졌으면 야후가 막힌 것이라 건너뜀)
    miss = [t for t in tickers if t not in out]
    if len(miss) <= 25:
        for t in miss:
            try:
                df = normalize_yf(yf.Ticker(t).history(period=period, interval="1d", auto_adjust=False))
            except Exception:
                continue
            if not df.empty:
                out[t] = df
    _mt_prune()
    mark("야후(지수·ETF·환율·원자재)", bool(out), f"{len(out)}/{len(tickers)}개 받음")
    return out


def _mt_prune() -> None:
    """(very에서 가져옴) yfinance 병렬 다운로드가 끝난 스레드를 목록에 계속 쌓아 두는 문제 → 끝난 것은 빼요."""
    try:
        import multitasking
        tasks = multitasking.config.get("TASKS")
        if isinstance(tasks, list) and tasks:
            tasks[:] = [t for t in tasks if getattr(t, "is_alive", lambda: False)()]
    except Exception:
        pass


# ─────────────────────────── stooq ───────────────────────────
def parse_stooq(text: str) -> dict | None:
    """stooq 간이 시세 CSV(Symbol,Date,Time,Open,High,Low,Close) → {date, close}."""
    try:
        row = pd.read_csv(io.StringIO(text)).iloc[0]
        close = float(row["Close"])
        if not close or pd.isna(close):
            return None
        return {"date": pd.Timestamp(str(row["Date"])), "close": close}
    except Exception:
        return None


_stooq_down = {"until": 0.0}


def stooq(sym: str) -> dict | None:
    if MOCK or time.time() < _stooq_down["until"]:
        return None
    try:
        r = session.get("https://stooq.com/q/l/", params={"s": sym, "f": "sd2t2ohlc", "h": "", "e": "csv"}, timeout=6)
        got = parse_stooq(r.text) if r.ok else None
        if got:
            mark("stooq(교차확인)", True, "")
        return got
    except Exception as e:
        _stooq_down["until"] = time.time() + 15 * 60     # 막혀 있으면 15분 동안은 다시 시도하지 않아요
        mark("stooq(교차확인)", False, e.__class__.__name__ + " (15분 동안 건너뜀)")
        return None


# ─────────────────────────── FRED ───────────────────────────
def parse_fred_csv(text: str) -> pd.DataFrame:
    """FRED fredgraph.csv → date, value (빈 값 '.' 제거)."""
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2:
        return pd.DataFrame(columns=["date", "value"])
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().reset_index(drop=True)


EMPTY_FRED = pd.DataFrame(columns=["date", "value"])
# FRED가 막히면 쓰는 다른 출처
DBNOMICS = {"CPIAUCSL": "BLS/cu/CUSR0000SA0", "CPILFESL": "BLS/cu/CUSR0000SA0L1E",
            "PAYEMS": "BLS/ce/CES0000000001", "UNRATE": "BLS/ln/LNS14000000"}
TREASURY = {"DGS2": "2 Yr", "DGS5": "5 Yr", "DGS10": "10 Yr", "DGS30": "30 Yr"}
YAHOO_RATE = {"DGS5": "^FVX", "DGS10": "^TNX", "DGS30": "^TYX"}


def _fred_key() -> str | None:
    k = os.environ.get("FRED_API_KEY")
    if k:
        return k
    try:
        import streamlit as st
        return st.secrets.get("FRED_API_KEY")
    except Exception:
        return None


def _fredgraph(series: str, start: str) -> pd.DataFrame:
    for params in ({"id": series, "cosd": start}, {"id": series}):
        try:
            r = session.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params=params, timeout=20)
            if r.ok and r.text.lstrip().lower().startswith(("observation_date", "date")):
                df = parse_fred_csv(r.text)
                if not df.empty:
                    return df[df["date"] >= start].reset_index(drop=True)
        except Exception:
            continue
    return EMPTY_FRED


def _fred_api(series: str, start: str) -> pd.DataFrame:
    key = _fred_key()
    if not key:
        return EMPTY_FRED
    try:
        r = session.get("https://api.stlouisfed.org/fred/series/observations",
                        params={"series_id": series, "api_key": key, "file_type": "json", "observation_start": start},
                        timeout=20)
        obs = r.json().get("observations", []) if r.ok else []
        df = pd.DataFrame([(o["date"], o["value"]) for o in obs], columns=["date", "value"])
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna().reset_index(drop=True)
    except Exception:
        return EMPTY_FRED


def parse_dbnomics(js: dict) -> pd.DataFrame:
    try:
        doc = js["series"]["docs"][0]
        df = pd.DataFrame({"date": pd.to_datetime(doc["period"], errors="coerce"),
                           "value": pd.to_numeric(pd.Series(doc["value"]), errors="coerce")})
        return df.dropna().reset_index(drop=True)
    except Exception:
        return EMPTY_FRED


def _dbnomics(series: str, start: str) -> pd.DataFrame:
    sid = DBNOMICS.get(series)
    if not sid:
        return EMPTY_FRED
    try:
        r = session.get(f"https://api.db.nomics.world/v22/series/{sid}", params={"observations": 1}, timeout=20)
        df = parse_dbnomics(r.json()) if r.ok else EMPTY_FRED
        return df[df["date"] >= start].reset_index(drop=True)
    except Exception:
        return EMPTY_FRED


def parse_treasury_csv(text: str, col: str) -> pd.DataFrame:
    """재무부 CSV에서 한 열. 명목금리 표는 '10 Yr', 실질금리 표는 '10 YR'처럼 대소문자가 달라서 맞춰 봐요."""
    df = pd.read_csv(io.StringIO(text))
    cols = {c.strip().lower(): c for c in df.columns}
    if "date" not in cols or col.lower() not in cols:
        return EMPTY_FRED
    out = pd.DataFrame({"date": pd.to_datetime(df[cols["date"]], errors="coerce"),
                        "value": pd.to_numeric(df[cols[col.lower()]], errors="coerce")})
    return out.dropna()


_treasury_cache: dict[tuple[int, str], str] = {}
# 시리즈 → [(표 종류, 열)] · 두 개면 앞 − 뒤. 실질금리(TIPS)는 재무부 실질금리 표, 기대인플레(BEI) = 명목 10년 − 실질 10년
NOMINAL, REAL = "daily_treasury_yield_curve", "daily_treasury_real_yield_curve"
TREASURY_MAP = {k: [(NOMINAL, v)] for k, v in TREASURY.items()} | {
    "T10Y2Y": [(NOMINAL, "10 Yr"), (NOMINAL, "2 Yr")],
    "DFII10": [(REAL, "10 Yr")], "DFII5": [(REAL, "5 Yr")],
    "T10YIE": [(NOMINAL, "10 Yr"), (REAL, "10 Yr")],
}


def _treasury_text(year: int, kind: str) -> str:
    if (year, kind) not in _treasury_cache:
        try:
            r = session.get(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                            f"daily-treasury-rates.csv/{year}/all",
                            params={"type": kind, "field_tdr_date_value": year, "_format": "csv"}, timeout=20)
            _treasury_cache[(year, kind)] = r.text if r.ok else ""
        except Exception:
            _treasury_cache[(year, kind)] = ""
    return _treasury_cache[(year, kind)]


def _treasury(series: str, start: str) -> pd.DataFrame:
    """미 재무부 일별 국채금리(명목·실질). 10Y−2Y, 기대인플레(명목−실질)도 여기서 계산."""
    spec = TREASURY_MAP.get(series)
    if not spec:
        return EMPTY_FRED
    frames = []
    for y in range(max(int(start[:4]), now_kst().year - 2), now_kst().year + 1):
        parts = [parse_treasury_csv(_treasury_text(y, kind), col) if _treasury_text(y, kind) else EMPTY_FRED
                 for kind, col in spec]
        if any(p.empty for p in parts):
            continue
        if len(parts) == 2:
            m = parts[0].merge(parts[1], on="date")
            frames.append(pd.DataFrame({"date": m["date"], "value": (m["value_x"] - m["value_y"]).round(3)}))
        else:
            frames.append(parts[0])
    if not frames:
        return EMPTY_FRED
    df = pd.concat(frames).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return df[df["date"] >= start].reset_index(drop=True)


# ─────────── FRED가 막힐 때: 원래 발표 기관에서 직접 ───────────
def parse_nyfed(js: dict) -> pd.DataFrame:
    rows = [(r.get("effectiveDate"), r.get("percentRate")) for r in (js or {}).get("refRates", [])]
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def parse_freddie(text: str) -> pd.DataFrame:
    """프레디맥 주간 모기지 금리 CSV(date, pmms30, …)."""
    df = pd.read_csv(io.StringIO(text))
    if "date" not in df or "pmms30" not in df:
        return EMPTY_FRED
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], errors="coerce", format="mixed"),
                        "value": pd.to_numeric(df["pmms30"], errors="coerce")})
    return out.dropna().sort_values("date").reset_index(drop=True)


def parse_umich(text: str) -> pd.DataFrame:
    """미시간대 소비자심리 CSV(Month, YYYY, ICS_ALL)."""
    lines = [l for l in text.splitlines() if l.strip()]
    head = next((i for i, l in enumerate(lines) if "YYYY" in l.upper()), None)
    if head is None:
        return EMPTY_FRED
    df = pd.read_csv(io.StringIO("\n".join(lines[head:])))
    cols = {c.strip().upper(): c for c in df.columns}
    m, y = cols.get("MONTH"), cols.get("YYYY")
    v = next((c for k, c in cols.items() if k.startswith("ICS")), None)
    if not (m and y and v):
        return EMPTY_FRED
    date = pd.to_datetime(df[m].astype(str).str.strip() + " " + df[y].astype(str).str.strip(), errors="coerce", format="%B %Y")
    out = pd.DataFrame({"date": date, "value": pd.to_numeric(df[v], errors="coerce")})
    return out.dropna().sort_values("date").reset_index(drop=True)


def _text(url: str, timeout: int = 30, **kw) -> str:
    r = session.get(url, timeout=timeout, **kw)
    r.raise_for_status()
    return r.text


def _nyfed(start: str) -> pd.DataFrame:
    end = (now_kst() + timedelta(days=1)).strftime("%Y-%m-%d")
    for url in (f"https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate={start}&endDate={end}",
                "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1000.json"):
        try:
            df = parse_nyfed(session.get(url, timeout=30).json())
            if not df.empty:
                return df
        except Exception:
            continue
    return EMPTY_FRED


# 노동통계국(BLS) 공개 API v1: 키 없이 한 번에 10년까지
BLS = {"CPIAUCSL": "CUSR0000SA0", "CPILFESL": "CUSR0000SA0L1E", "PAYEMS": "CES0000000001", "UNRATE": "LNS14000000"}


def parse_bls(js: dict) -> pd.DataFrame:
    rows = [(f'{o["year"]}-{o["period"][1:]}-01', o.get("value"))
            for s in (js or {}).get("Results", {}).get("series", []) for o in s.get("data", [])
            if str(o.get("period", "")).startswith("M") and o.get("period") != "M13"]
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def _bls(series: str):
    def fetch(start: str) -> pd.DataFrame:
        end = now_kst().year
        r = session.post("https://api.bls.gov/publicAPI/v1/timeseries/data/", timeout=30,
                         json={"seriesid": [BLS[series]], "startyear": str(max(int(start[:4]), end - 9)), "endyear": str(end)})
        js = r.json()
        if js.get("status") != "REQUEST_SUCCEEDED":
            raise ValueError(" ".join(js.get("message", []))[:120] or js.get("status"))
        return parse_bls(js)
    return fetch


# 경제분석국(BEA) 국민계정 전체 파일(키 없음). 근원 PCE 물가 = DPCCRG(월), 실질 GDP 성장률(연율) = A191RL(분기)
BEA = {"PCEPILFE": ("M", "DPCCRG"), "A191RL1Q225SBEA": ("Q", "A191RL")}
_bea_cache: dict[str, tuple[float, dict]] = {}


def parse_bea(text: str, code: str) -> pd.DataFrame:
    import csv
    rows = [next(csv.reader([l]))[1:3] for l in text.splitlines() if l.startswith(code + ",")]
    df = pd.DataFrame(rows, columns=["period", "value"])
    if df.empty:
        return EMPTY_FRED

    def when(p: str):
        p = p.strip()
        if "Q" in p:
            return pd.Period(p, freq="Q").start_time
        return pd.Timestamp(p.replace("M", "-") + "-01") if "M" in p else pd.Timestamp(p + "-01-01")
    out = pd.DataFrame({"date": df["period"].map(when),
                        "value": pd.to_numeric(df["value"].str.replace(",", ""), errors="coerce")})
    return out.dropna().sort_values("date").reset_index(drop=True)


def _bea(series: str):
    kind, code = BEA[series]

    def fetch(start: str) -> pd.DataFrame:
        hit = _bea_cache.get(kind)
        if not hit or time.time() - hit[0] > 6 * 3600:      # 큰 파일이라 필요한 줄만 남겨 6시간 보관
            text = _text(f"https://apps.bea.gov/national/Release/TXT/NipaData{kind}.txt", timeout=120)
            hit = (time.time(), {c: parse_bea(text, c) for k, c in BEA.values() if k == kind})
            _bea_cache[kind] = hit
        return hit[1].get(code, EMPTY_FRED)
    return fetch


def parse_g17(text: str, code: str = "B50001") -> pd.DataFrame:
    """연준 G.17 산업생산 파일(ip_sa.txt): '"B50001"  2025  103.1 103.4 …' (한 줄 = 한 해 12달)."""
    rows = []
    for line in text.splitlines():
        p = line.split()
        if len(p) > 2 and p[0] == f'"{code}"' and p[1].isdigit():
            rows += [(f"{p[1]}-{i:02d}-01", v) for i, v in enumerate(p[2:14], 1)]
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def parse_dol(text: str) -> pd.DataFrame:
    """노동부 주간 실업수당 XML(r539cyNational): 주마다 weekEnded와 신규 청구(계절조정 SA)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    rows = [(w.findtext("weekEnded"), w.findtext("InitialClaims/SA")) for w in root.iter("week")]
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y", errors="coerce")
    df["value"] = pd.to_numeric(df["value"].str.replace(",", "").str.strip(), errors="coerce")
    return df.dropna().sort_values("date").reset_index(drop=True)


def _dol(start: str) -> pd.DataFrame:
    r = session.post("https://oui.doleta.gov/unemploy/wkclaims/report.asp", timeout=60,
                     data={"level": "us", "final_yr": str(now_kst().year + 1), "strtdate": start[:4],
                           "enddate": str(now_kst().year), "filetype": "xml", "submit": "Submit"})
    r.raise_for_status()
    return parse_dol(r.text)


# FRED가 막힐 때 원래 발표 기관에서 직접 받는 곳: 시리즈 → (출처 이름, 받는 함수(start) → date·value)
ORIGIN = {
    "DFF": ("뉴욕연은", _nyfed),
    "MORTGAGE30US": ("프레디맥", lambda start: parse_freddie(_text("https://www.freddiemac.com/pmms/docs/PMMS_history.csv"))),
    "UMCSENT": ("미시간대", lambda start: parse_umich(_text("https://www.sca.isr.umich.edu/files/tbmics.csv"))),
    "ICSA": ("노동부(DOL)", _dol),
    "INDPRO": ("연준 G.17", lambda start: parse_g17(_text("https://www.federalreserve.gov/releases/g17/ipdisk/ip_sa.txt"))),
} | {k: ("노동통계국(BLS)", _bls(k)) for k in BLS} | {k: ("경제분석국(BEA)", _bea(k)) for k in BEA}


def _origin(series: str, start: str) -> pd.DataFrame:
    spec = ORIGIN.get(series)
    if not spec:
        return EMPTY_FRED
    try:
        df = spec[1](start)
        return df[df["date"] >= start].reset_index(drop=True)
    except Exception:
        return EMPTY_FRED


# ─────────── 저장소 파일(GitHub Actions가 하루 두 번 update_data.py로 받아 둔 값) ───────────
DATA_DIR = Path(__file__).resolve().parent / "data"
REPO_FRESH_DAYS = 4                     # 이보다 오래된 파일이면 실시간 출처를 먼저 시도해요
FRED_SRC: dict[str, str] = {}           # 시리즈 → 실제로 받은 출처 이름
_repo_cache: dict[str, tuple[float, object]] = {}


def _repo_read(name: str, reader):
    f = DATA_DIR / name
    try:
        mt = f.stat().st_mtime
    except OSError:
        return None
    if name not in _repo_cache or _repo_cache[name][0] != mt:
        try:
            _repo_cache[name] = (mt, reader(f))
        except Exception:
            _repo_cache[name] = (mt, None)
    return _repo_cache[name][1]


def repo_fred() -> pd.DataFrame:
    """data/fred.csv → id, date, value (없으면 빈 표)."""
    def read(f):
        df = pd.read_csv(f, dtype={"id": str})
        df["date"] = day(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna()
    df = _repo_read("fred.csv", read)
    return df if df is not None else pd.DataFrame(columns=["id", "date", "value"])


def repo_meta() -> dict:
    """{'at': 받은 시각(UTC), 'src': {시리즈: 원출처}, 'missing': [...], 'age': 지난 일수}."""
    m = _repo_read("fred_meta.json", lambda f: json.loads(f.read_text()))
    if not m:
        return {}
    at = pd.Timestamp(m.get("at")).tz_convert(KST) if m.get("at") else None
    return {**m, "at_kst": at, "age": (pd.Timestamp.now(tz=KST) - at).total_seconds() / 86400 if at is not None else None}


def _repo(series: str, start: str) -> pd.DataFrame:
    df = repo_fred()
    if df.empty:
        return EMPTY_FRED
    d = df[(df["id"] == series) & (df["date"] >= start)][["date", "value"]]
    return d.sort_values("date").reset_index(drop=True)


def _repo_name(series: str) -> str:
    m = repo_meta()
    orig = m.get("src", {}).get(series, "")
    when = f'{m["at_kst"]:%m/%d %H:%M}' if m.get("at_kst") is not None else ""
    return f"저장소 파일({when} 받음{', 원출처 ' + orig if orig else ''})"


def _yahoo_rate(series: str, start: str) -> pd.DataFrame:
    t = YAHOO_RATE.get(series)
    if not t:
        return EMPTY_FRED
    got = yahoo([t], period="2y").get(t)
    if got is None or got.empty:
        return EMPTY_FRED
    df = pd.DataFrame({"date": got["date"], "value": got["close"]})
    return df[df["date"] >= start].reset_index(drop=True)


MAX_AGE_DAYS = 300      # 마지막 값이 이보다 오래되면 '갱신이 멈춘 출처'로 봐요(분기 GDP도 넉넉히 들어오게)


def fresh(df: pd.DataFrame) -> bool:
    return not df.empty and (pd.Timestamp.today() - pd.Timestamp(df["date"].max())).days <= MAX_AGE_DAYS


def fred(series: str, days: int = 400, use_repo: bool = True) -> pd.DataFrame:
    """FRED 시리즈(date, value).
    순서: 저장소 파일(깃허브가 하루 두 번 받아 둔 값, 4일 안이면) → FRED → FRED API(키)
    → 발표 기관(BLS·BEA·연준·뉴욕연은·프레디맥·미시간대) → 미 재무부 → DBnomics → 야후 → 오래된 저장소 파일.
    마지막 값이 300일보다 오래된 결과는 버려요."""
    if MOCK:
        h = mock_history(series)
        out = pd.DataFrame({"date": h["date"], "value": (h["close"] / h["close"].iloc[0] * 3).round(2)})
        if days > 1000:      # 경제지표처럼 긴 기간은 월별로
            out["date"] = pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(out), freq="MS")
        return out.assign(date=day(out["date"]))
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    age = repo_meta().get("age") if use_repo else None
    if age is not None and age <= REPO_FRESH_DAYS:
        df = _repo(series, start)
        if fresh(df):
            FRED_SRC[series] = _repo_name(series)
            mark(f"경제지표 {series}", True, FRED_SRC[series])
            return df
    for name, fn in (("FRED", _fredgraph), ("FRED API", _fred_api), (ORIGIN.get(series, ("발표 기관",))[0], _origin),
                     ("미 재무부", _treasury), ("DBnomics(BLS)", _dbnomics), ("야후", _yahoo_rate)):
        df = fn(series, start)
        if not df.empty and not fresh(df):      # 갱신이 멈춘 출처(예: DBnomics의 BLS 사본)는 쓰지 않아요
            mark(f"경제지표 {series} · {name}", False, f'마지막 값 {df["date"].max():%Y-%m-%d}로 오래돼서 건너뜀')
            continue
        if not df.empty:
            FRED_SRC[series] = name
            mark(f"경제지표 {series}", True, name)
            return df.assign(date=day(df["date"]))
    if use_repo:
        df = _repo(series, start)
        if not df.empty:
            FRED_SRC[series] = _repo_name(series) + " · 오래된 값"
            mark(f"경제지표 {series}", True, FRED_SRC[series])
            return df
    mark(f"경제지표 {series}", False, "FRED·대체 출처 모두 실패")
    return EMPTY_FRED


# ─────────────────────────── 네이버(한국) ───────────────────────────
def parse_fchart(text: str) -> pd.DataFrame:
    """네이버 fchart XML → date, open, high, low, close, volume. item 형식: 날짜|시가|고가|저가|종가|거래량"""
    rows = []
    for item in re.findall(r'<item\s+data="([^"]+)"', text):
        p = item.split("|")
        if len(p) >= 5:
            rows.append((p + ["0"])[:6])
    df = pd.DataFrame(rows, columns=COLUMNS)
    if df.empty:
        return empty()
    df["date"] = day(pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce"))
    for k in COLUMNS[1:]:
        df[k] = pd.to_numeric(df[k], errors="coerce")
    df = df.dropna(subset=["date", "close"])
    df[["open", "high", "low"]] = df[["open", "high", "low"]].apply(lambda x: x.where(x > 0, df["close"]))
    df["volume"] = df["volume"].fillna(0)
    df = df[df["close"] > 0]
    return df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def naver(code: str, count: int = 500) -> pd.DataFrame:
    """종목코드(005930) 또는 KOSPI·KOSDAQ."""
    if MOCK:
        return mock_history(code, count)
    try:
        r = session.get("https://fchart.stock.naver.com/sise.nhn",
                        params={"symbol": code, "timeframe": "day", "count": count, "requestType": 0},
                        headers={"Referer": "https://finance.naver.com/"}, timeout=8)
        r.raise_for_status()
        raw = r.content
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp949", errors="replace")
        df = parse_fchart(text)
        mark("네이버 일봉", not df.empty, "" if not df.empty else f"{code} 빈 응답")
        return df
    except requests.RequestException as e:
        mark("네이버 일봉", False, f"{code} {e.__class__.__name__}")
        return empty()


# ─────────────────────────── RSS ───────────────────────────
def get_text(url: str, params: dict | None = None) -> str | None:
    host = requests.utils.urlparse(url).hostname or url
    try:
        r = session.get(url, params=params)
        mark(f"뉴스 {host}", r.ok, "" if r.ok else f"HTTP {r.status_code}")
        return r.text if r.ok else None
    except Exception as e:
        mark(f"뉴스 {host}", False, e.__class__.__name__)
        return None
