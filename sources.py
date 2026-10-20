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


def now_kst() -> datetime:
    return datetime.now(KST)


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


# ─────────────────────────── 가짜 데이터(MACRO_MOCK=1) ───────────────────────────
def mock_history(code: str, count: int = 300) -> pd.DataFrame:
    rng = random.Random(int(hashlib.md5(code.encode()).hexdigest()[:8], 16))
    dates = pd.bdate_range(end=now_kst().date(), periods=count)
    price, drift, rows = rng.uniform(20, 5_000), rng.uniform(-0.001, 0.002), []
    for _ in dates:
        o = price
        price = max(1.0, price * (1 + rng.gauss(drift, 0.015)))
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
        return {t: mock_history(t) for t in tickers}
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
    return out


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
        return parse_stooq(r.text) if r.ok else None
    except Exception:
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


def fred(series: str, days: int = 400) -> pd.DataFrame:
    """days일 전부터. 경제지표처럼 긴 역사가 필요하면 days를 크게."""
    if MOCK:
        h = mock_history(series)
        out = pd.DataFrame({"date": h["date"], "value": (h["close"] / h["close"].iloc[0] * 3).round(2)})
        if days > 1000:      # 경제지표처럼 긴 기간은 월별로
            out["date"] = pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(out), freq="MS")
        return out
    try:
        r = session.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                        params={"id": series, "cosd": (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")})
        return parse_fred_csv(r.text) if r.ok else pd.DataFrame(columns=["date", "value"])
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


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
        return parse_fchart(text)
    except requests.RequestException:
        return empty()


# ─────────────────────────── RSS ───────────────────────────
def get_text(url: str, params: dict | None = None) -> str | None:
    try:
        r = session.get(url, params=params)
        return r.text if r.ok else None
    except Exception:
        return None
