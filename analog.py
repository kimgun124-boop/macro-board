"""과거 비슷한 구간. 지금과 '고점 대비 낙폭'과 '이평선 위치'가 비슷했던 과거 날을 10년치에서 찾아,
그 뒤 20일·60일 동안 지수가 어떻게 움직였는지 세요. 모두 과거 시세로 계산한 사실이고, 미래를 보장하진 않아요.
"""
from __future__ import annotations

import pandas as pd

import alloc


def features(c: pd.Series) -> pd.DataFrame:
    c = c.astype(float)
    f = pd.DataFrame({"close": c})
    f["dd"] = (c / c.rolling(250, min_periods=120).max() - 1) * 100
    f["a50"] = c > c.rolling(50).mean()
    f["a200"] = c > c.rolling(200).mean()
    f["r20"] = (c / c.shift(20) - 1) * 100
    f["f20"] = (c.shift(-20) / c - 1) * 100
    f["f60"] = (c.shift(-60) / c - 1) * 100
    return f


def find(c: pd.Series | None, band: float = 3.0, gap: int = 20) -> dict | None:
    """낙폭 ±band%p, 50·200일선 위/아래가 같은 과거 날. 같은 사건이 겹치지 않게 gap 거래일 이상 띄워요."""
    if c is None or len(c) < 400:
        return None
    f = features(c).dropna(subset=["dd"])
    now = f.iloc[-1]
    past = f.iloc[:-60]
    m = past[(past["dd"].sub(now["dd"]).abs() <= band) & (past["a50"] == now["a50"]) & (past["a200"] == now["a200"])]
    m = m.dropna(subset=["f20"])
    picks, last = [], None
    for d, row in m.iterrows():
        if last is None or (f.index.get_loc(d) - f.index.get_loc(last)) >= gap:
            picks.append((d, row))
            last = d
    if not picks:
        return {"now": now, "n": 0, "rows": pd.DataFrame()}
    rows = pd.DataFrame([{"date": d, "dd": r["dd"], "r20": r["r20"], "f20": r["f20"], "f60": r["f60"]} for d, r in picks])
    st = lambda k: rows[k].dropna()
    return {"now": now, "n": len(rows), "rows": rows.sort_values("date", ascending=False).reset_index(drop=True),
            "f20": float(st("f20").mean()), "f20_up": float((st("f20") > 0).mean() * 100),
            "f60": float(st("f60").mean()) if len(st("f60")) else None,
            "f60_up": float((st("f60") > 0).mean() * 100) if len(st("f60")) else None,
            "worst20": float(st("f20").min()), "best20": float(st("f20").max()),
            "base20": float(f["f20"].dropna().mean()), "base20_up": float((f["f20"].dropna() > 0).mean() * 100)}


def all_for(px: dict) -> dict:
    """10년치(corr.fetch_long 결과: {'나스닥','코스피','코스닥'})에서."""
    out = {}
    for name in ("코스피", "나스닥", "코스닥"):
        df = px.get(name)
        s = alloc._close({name: df}, name) if df is not None else None
        out[name] = find(s)
    return out
