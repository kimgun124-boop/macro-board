"""나스닥 · 코스피 · 코스닥 상관관계.

- 기간: 3개월·6개월·1년·2년·3년·5년·10년 (일간 등락률의 피어슨 상관계수)
- 시차: 미국 장은 한국 장이 끝난 뒤에 열려요. 그래서 '나스닥 → 다음 날 코스피' (전날 밤 나스닥 등락과
  오늘 한국 등락)를 따로 봐요. 보통 이쪽이 더 높게 나와요.
- 최근 1~3일·1주·1달: 날짜별 등락을 나란히 놓고 같은 방향이었던 날 수, 누적 등락, 베타(나스닥 1% 움직일 때 몇 %)를 봐요.
  며칠짜리 상관계수는 숫자가 불안정해서 1달만 계수를 같이 보여 줘요.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import sources as S

SYMS = {"나스닥": "^IXIC", "코스피": "^KS11", "코스닥": "^KQ11"}
NAVER = {"코스피": "KOSPI", "코스닥": "KOSDAQ"}
WINDOWS = [("3개월", 63), ("6개월", 126), ("1년", 250), ("2년", 500), ("3년", 750), ("5년", 1250), ("10년", 2500)]
RECENT = [("1일", 1), ("2일", 2), ("3일", 3), ("1주", 5), ("1달", 21)]
# 비교 쌍: (기준, 대상, 시차) — 시차 True면 '전날 밤 나스닥 → 오늘 한국'
PAIRS = [("나스닥", "코스피", True), ("나스닥", "코스닥", True), ("나스닥", "코스피", False),
         ("나스닥", "코스닥", False), ("코스피", "코스닥", False)]


def fetch_long() -> dict[str, pd.DataFrame]:
    """10년치 일봉. 한국 지수는 야후가 비면 네이버로."""
    got = S.yahoo(list(SYMS.values()), period="10y")
    out = {n: got.get(t) for n, t in SYMS.items()}
    for n, code in NAVER.items():
        if out.get(n) is None or out[n].empty or len(out[n]) < 500:
            nv = S.naver(code, count=2600)
            if nv is not None and len(nv) > (0 if out.get(n) is None else len(out[n])):
                out[n] = nv
    return {n: df for n, df in out.items() if df is not None and not df.empty}


def returns(df: pd.DataFrame) -> pd.DataFrame:
    d = df[["date", "close"]].copy()
    d["date"] = S.day(d["date"])
    d = d.sort_values("date").drop_duplicates("date")
    d["ret"] = d["close"].astype(float).pct_change() * 100
    return d.dropna().reset_index(drop=True)


def align(base: pd.DataFrame, tgt: pd.DataFrame, lag: bool) -> pd.DataFrame:
    """대상 날짜마다 기준 등락을 붙여요. lag=True면 대상 날짜보다 '앞선' 가장 최근 기준 거래일(전날 밤 미국)."""
    a, b = returns(base)[["date", "ret"]], returns(tgt)[["date", "ret"]]
    if lag:
        a, b = a.assign(date=S.day(a["date"])), b.assign(date=S.day(b["date"]))
        m = pd.merge_asof(b.rename(columns={"ret": "tgt"}), a.rename(columns={"ret": "base", "date": "bdate"}),
                          left_on="date", right_on="bdate", allow_exact_matches=False, direction="backward")
        m = m[(m["date"] - m["bdate"]).dt.days <= 4]           # 연휴로 너무 벌어진 날은 빼요
    else:
        m = b.rename(columns={"ret": "tgt"}).merge(a.rename(columns={"ret": "base"}), on="date")
        m["bdate"] = m["date"]
    return m.dropna().reset_index(drop=True)


def stats(m: pd.DataFrame) -> dict | None:
    if len(m) < 1:
        return None
    x, y = m["base"].astype(float), m["tgt"].astype(float)
    corr = float(np.corrcoef(x, y)[0, 1]) if len(m) >= 10 and x.std() > 0 and y.std() > 0 else None
    beta = float(np.cov(x, y)[0, 1] / x.var()) if len(m) >= 10 and x.var() > 0 else None
    same = int(((x > 0) & (y > 0)).sum() + ((x < 0) & (y < 0)).sum())
    cum = lambda s: (float(np.prod(1 + s / 100)) - 1) * 100
    return {"n": len(m), "corr": corr, "beta": beta, "same": same, "base_cum": cum(x), "tgt_cum": cum(y),
            "start": m["date"].iloc[0], "end": m["date"].iloc[-1]}


def table(px: dict[str, pd.DataFrame], windows=WINDOWS) -> list[dict]:
    rows = []
    for b, t, lag in PAIRS:
        if b not in px or t not in px:
            continue
        m = align(px[b], px[t], lag)
        row = {"pair": f"{b} → {t}" + (" (전날 밤 → 오늘)" if lag else " (같은 날)"), "lag": lag, "cells": {}}
        for name, n in windows:
            row["cells"][name] = stats(m.tail(n)) if len(m) >= n * 0.8 else None
        rows.append(row)
    return rows


def recent_days(px: dict[str, pd.DataFrame], days: int = 21) -> pd.DataFrame:
    """최근 날짜별 등락: 한국 날짜 기준으로 전날 밤 나스닥, 코스피, 코스닥."""
    if "나스닥" not in px or "코스피" not in px:
        return pd.DataFrame()
    m = align(px["나스닥"], px["코스피"], True).rename(columns={"base": "나스닥(전날 밤)", "tgt": "코스피"})
    if "코스닥" in px:
        kq = returns(px["코스닥"])[["date", "ret"]].rename(columns={"ret": "코스닥"})
        m = m.merge(kq, on="date", how="left")
    return m.tail(days).iloc[::-1].reset_index(drop=True)


def rolling(px: dict[str, pd.DataFrame], b: str, t: str, lag: bool, win: int = 60) -> pd.DataFrame:
    """60거래일 이동 상관계수(흐름 차트용)."""
    if b not in px or t not in px:
        return pd.DataFrame(columns=["date", "value"])
    m = align(px[b], px[t], lag)
    v = m["base"].rolling(win).corr(m["tgt"])
    return pd.DataFrame({"date": m["date"], "value": v}).dropna().reset_index(drop=True)


def read(c: float | None) -> str:
    if c is None:
        return "—"
    a = abs(c)
    s = "매우 강함" if a >= 0.7 else "강함" if a >= 0.5 else "보통" if a >= 0.3 else "약함" if a >= 0.1 else "거의 없음"
    return s + ("" if c >= 0 else "(반대)")
