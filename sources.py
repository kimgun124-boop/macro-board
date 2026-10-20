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
import os
import random
import re
import threading
import time
from datetime import datetime, timedelta, timezone

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
    df.insert(0, "date", dates)
    return df


# ─────────────────────────── 야후 ───────────────────────────
def normalize_yf(hist: pd.DataFrame) -> pd.DataFrame:
    """yfinance 결과 → date, open, high, low, close, volume."""
    if hist is None or hist.empty or "Close" not in hist:
        return empty()
    idx = pd.DatetimeIndex(hist.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)

    def col(name):
        if name not in hist:
            return None
        v = hist[name]
        if isinstance(v, pd.DataFrame):
            v = v.iloc[:, 0]
        return pd.to_numeric(v, errors="coerce").values

    close = col("Close")
    df = pd.DataFrame({"date": idx.normalize(), "close": close})
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


def stooq(sym: str) -> dict | None:
    if MOCK:
        return None
    try:
        r = session.get("https://stooq.com/q/l/", params={"s": sym, "f": "sd2t2ohlc", "h": "", "e": "csv"})
        got = parse_stooq(r.text) if r.ok else None
        if got:
            mark("stooq(교차확인)", True, "")
        return got
    except Exception as e:
        mark("stooq(교차확인)", False, e.__class__.__name__)
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
    df = pd.read_csv(io.StringIO(text))
    if "Date" not in df or col not in df:
        return EMPTY_FRED
    out = pd.DataFrame({"date": pd.to_datetime(df["Date"], errors="coerce"), "value": pd.to_numeric(df[col], errors="coerce")})
    return out.dropna()


_treasury_cache: dict[int, str] = {}


def _treasury(series: str, start: str) -> pd.DataFrame:
    """미 재무부 일별 국채금리(2·5·10·30년). 10Y−2Y도 여기서 계산."""
    cols = {"T10Y2Y": ("10 Yr", "2 Yr")}.get(series) or ((TREASURY[series],) if series in TREASURY else None)
    if not cols:
        return EMPTY_FRED
    frames = []
    for y in range(max(int(start[:4]), now_kst().year - 2), now_kst().year + 1):
        if y not in _treasury_cache:
            try:
                r = session.get(f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                                f"daily-treasury-rates.csv/{y}/all",
                                params={"type": "daily_treasury_yield_curve", "field_tdr_date_value": y, "_format": "csv"},
                                timeout=20)
                _treasury_cache[y] = r.text if r.ok else ""
            except Exception:
                _treasury_cache[y] = ""
        text = _treasury_cache[y]
        if not text:
            continue
        if len(cols) == 2:
            a, b = parse_treasury_csv(text, cols[0]), parse_treasury_csv(text, cols[1])
            m = a.merge(b, on="date")
            frames.append(pd.DataFrame({"date": m["date"], "value": m["value_x"] - m["value_y"]}))
        else:
            frames.append(parse_treasury_csv(text, cols[0]))
    if not frames:
        return EMPTY_FRED
    df = pd.concat(frames).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return df[df["date"] >= start].reset_index(drop=True)


def _yahoo_rate(series: str, start: str) -> pd.DataFrame:
    t = YAHOO_RATE.get(series)
    if not t:
        return EMPTY_FRED
    got = yahoo([t], period="2y").get(t)
    if got is None or got.empty:
        return EMPTY_FRED
    df = pd.DataFrame({"date": got["date"], "value": got["close"]})
    return df[df["date"] >= start].reset_index(drop=True)


def fred(series: str, days: int = 400) -> pd.DataFrame:
    """FRED 시리즈(date, value). FRED가 막히면 FRED API(키) → DBnomics(BLS) → 미 재무부 → 야후 순서로 대신 받아요."""
    if MOCK:
        h = mock_history(series)
        out = pd.DataFrame({"date": h["date"], "value": (h["close"] / h["close"].iloc[0] * 3).round(2)})
        if days > 1000:      # 경제지표처럼 긴 기간은 월별로
            out["date"] = pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(out), freq="MS")
        return out
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    for name, fn in (("FRED", _fredgraph), ("FRED API", _fred_api), ("DBnomics(BLS)", _dbnomics),
                     ("미 재무부", _treasury), ("야후", _yahoo_rate)):
        df = fn(series, start)
        if not df.empty:
            mark(f"경제지표 {series}", True, name)
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
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
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
