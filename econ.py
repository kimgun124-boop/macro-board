"""경제지표(FRED)와 발표일 지수 반응.

- 값: FRED 시리즈를 config.ECON의 how(yoy·mom·diff·level)로 바꿔 보여 줘요.
- 발표일: FRED_API_KEY가 있으면 FRED 발표 일정(정확), 없으면 규칙으로 추정해요
  (고용 = 다음 달 첫 금요일, CPI = 다음 달 둘째 주 수요일 무렵, PCE = 다음 달 마지막 금요일).
- 반응: 미국·유럽 지수는 발표 당일, 아시아 지수는 다음 거래일 등락(미국 발표가 한국시간 밤이라서).
- '뜨거움/식음'은 시장 예상치가 아니라 직전 값과 비교한 거예요. 예상치 대비는 AI 해설이 기사로 찾아요.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import config as C
import sources as S


def transform(df: pd.DataFrame, how: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])
    d = df.sort_values("date").reset_index(drop=True).copy()
    v = d["value"].astype(float)
    if how == "yoy":
        # 날짜 간격과 상관없이 1년 전 값과 비교
        past = pd.merge_asof(d[["date"]].assign(date=d["date"] - pd.DateOffset(years=1)), d, on="date")["value"]
        d["value"] = (v / past.values - 1) * 100
    elif how == "mom":
        d["value"] = v.pct_change() * 100
    elif how == "diff":
        d["value"] = v.diff()
    return d.dropna().reset_index(drop=True)


def fetch_series() -> dict[str, pd.DataFrame]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        raw = list(pool.map(lambda e: S.fred(e["id"], days=365 * 12), C.ECON))
    return {e["id"]: transform(r, e["how"]) for e, r in zip(C.ECON, raw)}


def _api_key() -> str | None:
    k = os.environ.get("FRED_API_KEY")
    if k:
        return k
    try:
        import streamlit as st
        return st.secrets.get("FRED_API_KEY")
    except Exception:
        return None


def release_dates(rid: int) -> list[pd.Timestamp] | None:
    """FRED 발표 일정(키가 있을 때만)."""
    key = _api_key()
    if not key or S.MOCK:
        return None
    try:
        r = S.session.get("https://api.stlouisfed.org/fred/release/dates",
                          params={"release_id": rid, "api_key": key, "file_type": "json", "sort_order": "desc",
                                  "limit": 60, "include_release_dates_with_no_data": "false"})
        if not r.ok:
            return None
        return sorted(pd.Timestamp(x["date"]) for x in r.json().get("release_dates", []))
    except Exception:
        return None


def _rule_date(ref: pd.Timestamp, kind: str) -> pd.Timestamp:
    """기준월(ref) 다음 달의 추정 발표일."""
    nxt = (ref + pd.offsets.MonthBegin(1)).normalize()
    if kind == "jobs":
        return nxt + pd.offsets.Week(weekday=4) if nxt.weekday() != 4 else nxt
    if kind == "cpi":
        first_wed = nxt if nxt.weekday() == 2 else nxt + pd.offsets.Week(weekday=2)
        return first_wed + pd.Timedelta(days=7)
    end = nxt + pd.offsets.MonthEnd(0)
    return end - pd.offsets.Week(weekday=4) if end.weekday() != 4 else end


def _ret_on(px: pd.DataFrame | None, day: pd.Timestamp, after: bool, absolute: bool) -> float | None:
    """day(또는 다음 거래일)의 1일 변화."""
    if px is None or len(px) < 3:
        return None
    d = px[["date", "close"]].copy()
    d["date"] = S.day(d["date"])
    d = d.reset_index(drop=True)
    idx = d.index[d["date"] > day] if after else d.index[d["date"] >= day]
    if not len(idx):
        return None
    i = idx[0]
    if i == 0 or (not after and d["date"][i] - day > pd.Timedelta(days=3)):
        return None
    a, b = float(d["close"][i - 1]), float(d["close"][i])
    return (b - a) if absolute else (b / a - 1) * 100


def releases(e: dict, series: pd.DataFrame, px: dict, n: int = 12) -> dict:
    """최근 n번 발표: 값·직전 값·뜨거움/식음·지수 반응."""
    if series is None or series.empty or not e.get("release"):
        return {"rows": [], "exact": False}
    s = series.copy()
    s["ref"] = s["date"].dt.to_period("M").dt.to_timestamp()
    s = s.groupby("ref", as_index=False)["value"].last()          # 월 단위로(목업·주간 자료 대비)
    exact = release_dates(e["rid"])
    rows = []
    for i in range(max(1, len(s) - n), len(s)):
        ref, val, prev = s["ref"][i], float(s["value"][i]), float(s["value"][i - 1])
        if exact:
            cand = [d for d in exact if d > ref + pd.offsets.MonthEnd(0)]
            day = cand[0] if cand else None
        else:
            day = _rule_date(ref, e["release"])
        if day is None or day > pd.Timestamp.today():
            continue
        if e["how"] == "diff":       # 고용: 직전 3개월 평균보다 많이 늘었나
            base = float(s["value"][max(0, i - 3):i].mean())
        else:
            base = prev
        up = val > base
        hot = up if e["hot"] == "up" else not up
        react = {sym: _ret_on(px.get(sym), day, asia, sym == "^TNX") for sym, _, asia in C.REACT}
        rows.append({"ref": ref, "day": day, "value": val, "prev": prev, "base": base, "hot": hot, "react": react})
    return {"rows": rows[::-1], "exact": bool(exact)}


def reaction_stats(rows: list[dict]) -> list[dict]:
    """뜨거울 때/식을 때 평균 반응."""
    out = []
    for sym, name, asia in C.REACT:
        hot = [r["react"][sym] for r in rows if r["hot"] and r["react"].get(sym) is not None]
        cool = [r["react"][sym] for r in rows if not r["hot"] and r["react"].get(sym) is not None]
        avg = lambda xs: sum(xs) / len(xs) if xs else None
        out.append({"sym": sym, "name": name, "asia": asia, "hot": avg(hot), "cool": avg(cool),
                    "n_hot": len(hot), "n_cool": len(cool)})
    return out


def sahm(unrate: pd.DataFrame) -> float | None:
    """삼의 법칙: 실업률 3개월 평균 − 직전 12개월 중 3개월 평균의 최저. 0.5 이상이면 침체 신호."""
    if unrate is None or len(unrate) < 15:
        return None
    m = unrate.set_index("date")["value"].resample("MS").last().dropna()
    a3 = m.rolling(3).mean()
    if len(a3.dropna()) < 13:
        return None
    return float(a3.iloc[-1] - a3.iloc[-13:-1].min())


def summary(series: dict[str, pd.DataFrame]) -> dict[str, dict | None]:
    out = {}
    for e in C.ECON:
        s = series.get(e["id"])
        if s is None or len(s) < 2:
            out[e["id"]] = None
            continue
        last, prev = float(s["value"].iloc[-1]), float(s["value"].iloc[-2])
        y = s[s["date"] >= s["date"].iloc[-1] - pd.DateOffset(years=1)]
        out[e["id"]] = {"last": last, "prev": prev, "date": s["date"].iloc[-1], "chg": last - prev,
                        "y_hi": float(y["value"].max()), "y_lo": float(y["value"].min())}
    return out
