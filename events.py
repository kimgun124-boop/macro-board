"""다가오는 이벤트(FOMC·CPI·고용·PCE·옵션 만기)와, 과거 같은 이벤트 날 지수가 어떻게 움직였는지.

- FOMC: 연준이 공지한 결정 발표일(미국 날짜). 한국에선 다음 날 새벽에 나와요.
- CPI·고용·PCE: 발표 규칙으로 계산한 '추정일'(실제와 하루 이틀 다를 수 있어요. FRED_API_KEY가 있으면 경제지표 탭이 실제 날짜를 써요).
- 옵션 만기: 한국은 매월 둘째 목요일(3·6·9·12월은 선물까지 겹치는 동시만기), 미국은 매월 셋째 금요일.
"""
from __future__ import annotations

import pandas as pd

import econ
import sources as S

FOMC = [pd.Timestamp(d) for d in (
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09")]
WHY = {
    "fomc": "금리 결정·점도표. 블로그: 이벤트 앞엔 시나리오 두 갈래(통과하면 쌍바닥 반등, 충격이면 전저점·200일선까지 열어 두기)",
    "cpi": "물가가 높게 나오면 금리 인하 기대↓ → 10년물↑ → 성장주 부담",
    "jobs": "고용이 너무 강하면 금리 부담, 너무 약하면 경기 우려",
    "pce": "연준이 가장 중요하게 보는 물가",
    "kr_opt": "옵션 만기일엔 프로그램 매매로 지수가 크게 흔들릴 수 있어요",
    "kr_quad": "선물·옵션 동시만기: 외국인 선물 포지션 정리로 변동성↑",
    "us_opt": "미국 옵션 만기(3·6·9·12월은 쿼드러플 위칭)",
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    shift = (weekday - first.weekday()) % 7
    return first + pd.Timedelta(days=shift + 7 * (n - 1))


def _us_dst(d: pd.Timestamp) -> bool:
    """미국 서머타임(3월 둘째 일요일 ~ 11월 첫째 일요일)."""
    start = _nth_weekday(d.year, 3, 6, 2)
    end = _nth_weekday(d.year, 11, 6, 1)
    return start <= d < end


def calendar(today: pd.Timestamp, days: int = 35) -> list[dict]:
    today = today.normalize()
    end = today + pd.Timedelta(days=days)
    out = []
    for d in FOMC:
        if today <= d + pd.Timedelta(days=1) and d <= end:
            kst = d + pd.Timedelta(days=1)
            out.append({"date": d, "kst": kst, "time": f"{kst:%m/%d} 새벽 {'3' if _us_dst(d) else '4'}시(한국)", "name": "FOMC 금리 결정",
                        "kind": "fomc", "est": False})
    months = pd.period_range(today - pd.Timedelta(days=62), end, freq="M")
    for p in months:
        ref = p.to_timestamp()
        for kind, name in (("cpi", "미국 CPI"), ("jobs", "미국 고용(비농업·실업률)"), ("pce", "미국 PCE 물가")):
            d = econ._rule_date(ref, kind)
            if today <= d <= end:
                out.append({"date": d, "kst": d, "time": f"{d:%m/%d} 밤 {'9' if _us_dst(d) else '10'}시 30분(한국)",
                            "name": f"{name} ({ref:%m}월분)", "kind": kind, "est": True})
        y, m = p.year, p.month
        kr = _nth_weekday(y, m, 3, 2)
        if today <= kr <= end:
            quad = m in (3, 6, 9, 12)
            out.append({"date": kr, "kst": kr, "time": f"{kr:%m/%d} 장중", "name": "한국 선물·옵션 동시만기" if quad else "한국 옵션 만기",
                        "kind": "kr_quad" if quad else "kr_opt", "est": False})
        us = _nth_weekday(y, m, 4, 3)
        if today <= us <= end:
            out.append({"date": us, "kst": us + pd.Timedelta(days=1), "time": f"{us:%m/%d} 미국 장중",
                        "name": "미국 옵션 만기" + (" (쿼드러플 위칭)" if m in (3, 6, 9, 12) else ""), "kind": "us_opt", "est": False})
    for e in out:
        e["dday"] = (e["kst"].normalize() - today).days
        e["why"] = WHY[e["kind"]]
    seen, uniq = set(), []
    for e in sorted(out, key=lambda e: e["kst"]):
        k = (e["name"], e["date"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


def fomc_reaction(px: dict, today: pd.Timestamp) -> dict | None:
    """지난 FOMC 날: 나스닥(발표 당일 미국 장)·코스피(다음 한국 장) 등락."""
    rows = []
    for d in [d for d in FOMC if d < today.normalize()]:
        nq = econ._ret_on(px.get("^IXIC"), d, after=False, absolute=False)
        ks = econ._ret_on(px.get("^KS11"), d, after=True, absolute=False)
        tn = econ._ret_on(px.get("^TNX"), d, after=False, absolute=True)
        if nq is None and ks is None:
            continue
        rows.append({"date": d, "nasdaq": nq, "kospi": ks, "tnx": tn})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    stat = lambda c: None if df[c].dropna().empty else {"avg": float(df[c].mean()), "abs": float(df[c].abs().mean()),
                                                       "up": int((df[c] > 0).sum()), "n": int(df[c].notna().sum())}
    return {"rows": df.sort_values("date", ascending=False).reset_index(drop=True), "nasdaq": stat("nasdaq"), "kospi": stat("kospi")}


def expiry_reaction(px: dict, today: pd.Timestamp, n: int = 12) -> dict | None:
    """지난 한국 옵션 만기일 코스피 등락(절대값 평균)과 보통 날 비교."""
    df = px.get("^KS11")
    if df is None or len(df) < 60:
        return None
    d = df[["date", "close"]].copy()
    d["date"] = S.day(d["date"])
    d["r"] = d["close"].astype(float).pct_change() * 100
    d = d.dropna()
    days = []
    for p in pd.period_range(d["date"].iloc[0], today, freq="M"):
        x = _nth_weekday(p.year, p.month, 3, 2)
        if x < today.normalize():
            days.append(x)
    hit = d[d["date"].isin(days[-n:])]
    if hit.empty:
        return None
    return {"n": len(hit), "abs": float(hit["r"].abs().mean()), "normal": float(d["r"].tail(250).abs().mean())}
