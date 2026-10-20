"""계좌 비중 판단. 신호 12개를 점수로 바꿔 더하고(100점 만점), 점수 구간으로 주식 비중을 정해요.

규칙은 knowledge.md(보내 주신 블로그 정리)의 추세추종·레드라인 기준을 숫자로 옮긴 거예요.
- 추세 35점: 나스닥·S&P·코스피 이평선 위치, 삼성전자·SK하이닉스(전닉)
- 금리·유가 25점: 미 10년물(5% 레드라인), WTI
- 위험 20점: VIX, 하이일드 스프레드, 나스닥 -3% 패닉
- 수급·폭 20점: 외국인 코스피 순매수, 미국 섹터 폭, 원/달러
- 상한(레드라인): 10년물 5% 이상이면 '축소' 위로 못 가요. 나스닥 -3%나 전닉 동반 하락이면 '중립' 위로 못 가요.
받지 못한 신호는 빼고, 받은 신호의 만점 합으로 다시 100점에 맞춰요.
점수표를 바꾸고 싶으면 아래 숫자만 고치면 돼요.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C

# (하한 점수, 이름, 주식 비중, 색, 한 줄)
BANDS = [
    (80, "공격", "80~100%", "#D6333B", "추세·금리·수급이 다 받쳐 줘요. 주도주 비중을 끝까지 실어요."),
    (65, "확대", "60~80%", "#E0672B", "추세가 좋고 경고등이 적어요. 강한 섹터 위주로 늘려요."),
    (50, "중립", "40~60%", "#B7791F", "신호가 갈려요. 50일선 위 종목만 들고 나머지는 기다려요."),
    (35, "축소", "20~40%", "#1F66C9", "경고가 더 많아요. 신규 매수를 줄이고 손절선을 올려요."),
    (0, "방어", "0~20%", "#1B3F7A", "하락 추세와 위험 신호가 겹쳐요. 현금을 크게 둬요."),
]
GROUPS = ["추세", "금리·유가", "위험", "수급·폭"]
STAGE_NAME = {1.0: "상승 추세", 0.8: "추세 속 눌림", 0.55: "회복 시도", 0.5: "중기 조정(10일선 회복)",
              0.35: "중기 조정", 0.15: "하락 추세(10일선 회복)", 0.0: "하락 추세"}
KR_IDX, US_IDX = ("^KS11", "naver:KOSPI"), ("^IXIC", "^GSPC")
CORE = (("005930", "삼성전자"), ("000660", "SK하이닉스"))


def band(score: float) -> dict:
    for lo, name, eq, col, say in BANDS:
        if score >= lo:
            return {"name": name, "equity": eq, "color": col, "say": say, "lo": lo}
    return band(0)


# ─────────────────────────── 점수 규칙(숫자 하나 → 점수) ───────────────────────────
def stage_series(c: pd.Series) -> pd.Series:
    """이평선 위치 → 0~1점. 정배열 1, 20일선 아래 눌림 0.8, 회복 시도 0.55, 중기 조정 0.35, 하락 0 (10일선 회복 +0.15)."""
    c = c.astype(float)
    ma = {n: c.rolling(n).mean() for n in (10, 20, 50, 200)}
    a10, a20, a50 = c > ma[10], c > ma[20], c > ma[50]
    a200 = (c > ma[200]) | (ma[200].isna() & a50)
    out = np.select([a50 & a200 & a20, a50 & a200, a50 & ~a200, ~a50 & a200 & a10, ~a50 & a200, a10],
                    [1.0, 0.8, 0.55, 0.5, 0.35, 0.15], 0.0)
    s = pd.Series(out, index=c.index)
    s[ma[50].isna()] = np.nan
    return s


def p_rate(v: float, d20: float | None = None) -> int:
    p = 15 if v < 4.3 else 12 if v < 4.5 else 8 if v < 4.8 else 4 if v < 5.0 else 0
    return max(0, p - 2) if d20 is not None and d20 > 0.25 else p


def p_oil(v: float, d20: float | None = None) -> int:
    p = 10 if v < 75 else 8 if v < 85 else 5 if v < 95 else 2 if v < 105 else 0
    if d20 is not None:
        p += -2 if d20 > 10 else 2 if d20 < -10 else 0
    return min(10, max(0, p))


def p_vix(v: float) -> int:
    return 7 if v < 15 else 6 if v < 18 else 4 if v < 22 else 2 if v < 28 else 1 if v < 35 else 0


def p_hy(level: float, a20: float | None) -> int:
    a = a20 or 0
    p = 6 if (level < 3.5 and a < 0.2) else 5 if a < 0.2 else 3 if a < 0.5 else 0
    return min(p, 1) if level > 5 else p


def credit_proxy(sm: dict) -> float | None:
    """하이일드 ETF(HYG) − 국채 ETF(IEF) 20일 등락 차이. 음수가 크면 신용 위험이 커지는 중."""
    h, i = sm.get("HYG"), sm.get("IEF")
    if not h or not i or h.get("d20") is None or i.get("d20") is None:
        return None
    return h["d20"] - i["d20"]


def p_credit_proxy(rel: float) -> int:
    return 6 if rel >= 1 else 5 if rel >= 0 else 3 if rel >= -1.5 else 1 if rel >= -3 else 0


def p_panic(worst: float) -> int:
    return 7 if worst > -3 else 0


def p_foreign(f5: float, f20: float) -> int:
    return 8 if f5 > 0 and f20 > 0 else 5 if f5 > 0 else 3 if f20 > 0 else 0


def p_breadth(share: float) -> int:
    return 6 if share >= 0.6 else 4 if share >= 0.45 else 2 if share >= 0.3 else 0


def p_krw(d20: float) -> int:
    return 6 if d20 <= -1 else 5 if d20 <= 0.5 else 3 if d20 <= 2 else 1 if d20 <= 4 else 0


# ─────────────────────────── 데이터 꺼내기 ───────────────────────────
def _close(px: dict, *keys) -> pd.Series | None:
    for k in keys:
        df = px.get(k)
        if df is not None and len(df) >= 30:
            d = df[["date", "close"]].copy()
            d["date"] = pd.to_datetime(d["date"]).dt.normalize()
            s = d.drop_duplicates("date", keep="last").set_index("date")["close"].astype(float).sort_index()
            return s
    return None


def _tnx(px: dict) -> pd.Series | None:
    s = _close(px, "^TNX")
    if s is None:
        return None
    if s.median() > 20:           # 예전 야후 표기(×10)
        s = s / 10
    return s if 0 < s.median() < 20 else None


def _ret(s: pd.Series | None, n: int) -> float | None:
    return float((s.iloc[-1] / s.iloc[-1 - n] - 1) * 100) if s is not None and len(s) > n else None


def _sig(key, group, name, value, pts, mx, why, nxt=None, gain=0):
    return {"key": key, "group": group, "name": name, "value": value, "pts": pts, "max": mx, "why": why,
            "next": nxt, "gain": gain}


def _stage_sig(key, name, s, mx):
    if s is None:
        return _sig(key, "추세", name, "—", None, mx, "받지 못함")
    st = stage_series(s)
    v = st.iloc[-1]
    if pd.isna(v):
        return _sig(key, "추세", name, "—", None, mx, "기간 부족")
    hi = s.tail(250).max()
    nxt, gain = None, 0
    if v < 1:
        ma20, ma50 = s.tail(20).mean(), s.tail(50).mean()
        if v <= 0.35:
            nxt, gain = f"50일선({ma50:,.0f}) 회복", round(mx * (0.55 - v))
        else:
            nxt, gain = f"20일선({ma20:,.0f}) 회복", round(mx * (1 - v))
    return _sig(key, "추세", name, STAGE_NAME.get(round(float(v), 2), "—"), round(mx * float(v), 1), mx,
                f"고점 대비 {(s.iloc[-1] / hi - 1) * 100:+.1f}%", nxt, gain)


# ─────────────────────────── 지금 점수 ───────────────────────────
def signals(snap: dict, fl: dict | None = None) -> list[dict]:
    px, sm, fred = snap.get("px", {}), snap["sm"], snap.get("fred", {})
    out = [
        _stage_sig("nasdaq", "나스닥", _close(px, "^IXIC"), 10),
        _stage_sig("spx", "S&P 500", _close(px, "^GSPC"), 5),
        _stage_sig("kospi", "코스피", _close(px, *KR_IDX), 10),
    ]
    # 전닉: 두 종목 평균
    cs = [(n, _close(px, c)) for c, n in CORE]
    st = [(n, stage_series(s).iloc[-1]) for n, s in cs if s is not None]
    st = [(n, v) for n, v in st if not pd.isna(v)]
    if st:
        v = sum(x for _, x in st) / len(st)
        label = " · ".join(f"{n} {STAGE_NAME.get(round(float(x), 2), '')}" for n, x in st)
        vols = []
        for n, s in cs:
            if s is not None and len(s) > 61:
                r = s.pct_change()
                vols.append(r.tail(20).std() < r.tail(60).std())
        calm = "변동성 축소 중(반등 첫 신호)" if vols and all(vols) else "변동성 확대 중" if vols else ""
        out.append(_sig("core", "추세", "전닉(삼성·하이닉스)", label, round(10 * v, 1), 10, calm,
                        "두 종목 20일선 회복" if v < 0.8 else None, round(10 * (0.8 - v)) if v < 0.8 else 0))
    else:
        out.append(_sig("core", "추세", "전닉(삼성·하이닉스)", "—", None, 10, "받지 못함"))

    ten = fred.get("DGS10") or sm.get("^TNX")
    if ten:
        v, d = ten["last"], ten.get("a20")
        p = p_rate(v, d)
        nxt = next(((f"{t:.1f}% 아래로", p_rate(t - 0.01, d) - p) for t in (5.0, 4.8, 4.5, 4.3) if v >= t), None)
        out.append(_sig("rate", "금리·유가", "미 10년물", f"{v:.2f}%", p, 15,
                        ("5% 레드라인 위" if v >= 5 else "레드라인 5% 아래") + (f" · 20일 {d:+.2f}%p" if d is not None else ""),
                        *(nxt or (None, 0))))
    else:
        out.append(_sig("rate", "금리·유가", "미 10년물", "—", None, 15, "받지 못함"))

    oil = _close(px, "CL=F")
    if oil is not None:
        v, d = float(oil.iloc[-1]), _ret(oil, 20)
        p = p_oil(v, d)
        nxt = next(((f"WTI {t}달러 아래로", p_oil(t - 0.1, d) - p) for t in (105, 95, 85, 75) if v >= t), None)
        out.append(_sig("oil", "금리·유가", "WTI 유가", f"{v:.1f}달러", p, 10,
                        f"20일 {d:+.1f}%" if d is not None else "", *(nxt or (None, 0))))
    else:
        out.append(_sig("oil", "금리·유가", "WTI 유가", "—", None, 10, "받지 못함"))

    vix = sm.get("^VIX")
    if vix:
        v = vix["last"]
        p = p_vix(v)
        nxt = next(((f"VIX {t} 아래로", p_vix(t - 0.01) - p) for t in (35, 28, 22, 18, 15) if v >= t), None)
        out.append(_sig("vix", "위험", "VIX", f"{v:.1f}", p, 7,
                        "공포" if v >= 30 else "불안" if v >= 20 else "평온", *(nxt or (None, 0))))
    else:
        out.append(_sig("vix", "위험", "VIX", "—", None, 7, "받지 못함"))

    hy = fred.get("BAMLH0A0HYM2")
    if hy:
        p = p_hy(hy["last"], hy.get("a20"))
        out.append(_sig("hy", "위험", "하이일드 스프레드", f'{hy["last"]:.2f}%', p, 6,
                        f'20일 {hy.get("a20") or 0:+.2f}%p · ' + ("신용 불안" if p <= 3 else "신용 안정"),
                        "20일 변화 +0.2%p 아래로" if p < 5 else None, 5 - p if p < 5 else 0))
    elif credit_proxy(sm) is not None:
        rel = credit_proxy(sm)
        p = p_credit_proxy(rel)
        out.append(_sig("hy", "위험", "신용(HYG−IEF 대체)", f"20일 {rel:+.1f}%p", p, 6,
                        "FRED가 막혀 ETF로 대신 봐요 · " + ("신용 불안" if p <= 3 else "신용 안정"),
                        "하이일드가 국채보다 덜 빠지기" if p < 5 else None, 5 - p if p < 5 else 0))
    else:
        out.append(_sig("hy", "위험", "하이일드 스프레드", "—", None, 6, "받지 못함"))

    nq = _close(px, "^IXIC")
    if nq is not None and len(nq) > 6:
        worst = float((nq.pct_change().tail(5) * 100).min())
        p = p_panic(worst)
        out.append(_sig("panic", "위험", "나스닥 -3% 패닉", f"5일 최악 {worst:+.1f}%", p, 7,
                        "패닉 신호 발생" if p == 0 else "패닉 없음", "5거래일 동안 -3% 없이" if p == 0 else None, 7 - p))
    else:
        out.append(_sig("panic", "위험", "나스닥 -3% 패닉", "—", None, 7, "받지 못함"))

    df = (fl or {}).get("코스피")
    if df is not None and not df.empty and "외국인" in df:
        f5, f20 = float(df.tail(5)["외국인"].sum()), float(df.tail(20)["외국인"].sum())
        p = p_foreign(f5, f20)
        out.append(_sig("foreign", "수급·폭", "외국인(코스피)", f"5일 {f5:+,.0f}억", p, 8, f"20일 {f20:+,.0f}억",
                        "5일 순매수 전환" if f5 <= 0 else ("20일 합계 플러스" if f20 <= 0 else None), 8 - p))
    else:
        out.append(_sig("foreign", "수급·폭", "외국인(코스피)", "—", None, 8, "받지 못함"))

    secs = [stage_series(s).iloc[-1] for s in (_close(px, t) for t, _ in C.SECTORS) if s is not None]
    secs = [v for v in secs if not pd.isna(v)]
    if secs:
        n50 = sum(1 for v in secs if v >= 0.55)
        share = n50 / len(secs)
        p = p_breadth(share)
        out.append(_sig("breadth", "수급·폭", "미국 섹터 폭", f"{n50}/{len(secs)} 50일선 위", p, 6,
                        "폭이 넓음" if p >= 4 else "소수 쏠림", f"{int(np.ceil(len(secs) * 0.6))}개 이상 50일선 위" if p < 6 else None,
                        6 - p))
    else:
        out.append(_sig("breadth", "수급·폭", "미국 섹터 폭", "—", None, 6, "받지 못함"))

    krw = _close(px, "KRW=X")
    if krw is not None:
        d = _ret(krw, 20)
        p = p_krw(d)
        out.append(_sig("krw", "수급·폭", "원/달러", f"{krw.iloc[-1]:,.0f}원", p, 6,
                        f"20일 {d:+.1f}% · " + ("원화 약세(외국인 부담)" if d > 0.5 else "원화 안정"),
                        "20일 변화 +0.5% 아래" if p < 5 else None, 5 - p if p < 5 else 0))
    else:
        out.append(_sig("krw", "수급·폭", "원/달러", "—", None, 6, "받지 못함"))
    return out


def caps(sigs: list[dict], snap: dict) -> list[tuple[int, str]]:
    """레드라인: (점수 상한, 이유)."""
    by = {s["key"]: s for s in sigs}
    out = []
    ten = snap.get("fred", {}).get("DGS10") or snap["sm"].get("^TNX")
    if ten and ten["last"] >= 5:
        out.append((49, f"미 10년물 {ten['last']:.2f}% ≥ 5% → 실적과 상관없이 비중 축소(블로그 레드라인)"))
    if by.get("panic", {}).get("pts") == 0:
        out.append((64, "나스닥 -3% 패닉 신호 → 신규 매수 멈춤"))
    core = by.get("core", {})
    if core.get("pts") is not None and core["pts"] <= 1.5:
        out.append((64, "전닉이 같이 하락 추세 → 주도주가 가장 약함(미너비니 경고)"))
    return out


def build(snap: dict, fl: dict | None = None) -> dict:
    sigs = signals(snap, fl)
    got = [s for s in sigs if s["pts"] is not None]
    mx = sum(s["max"] for s in got)
    raw = sum(s["pts"] for s in got) / mx * 100 if mx else 50.0
    cp = caps(sigs, snap)
    score = min([raw] + [c for c, _ in cp])
    groups = {}
    for g in GROUPS:
        gs = [s for s in got if s["group"] == g]
        m = sum(s["max"] for s in gs)
        groups[g] = (sum(s["pts"] for s in gs), m) if m else (None, sum(s["max"] for s in sigs if s["group"] == g))
    lost = sorted(got, key=lambda s: -(s["max"] - s["pts"]))
    good = sorted(got, key=lambda s: -(s["pts"] / s["max"]))
    triggers = [(s["next"], s["gain"], s["name"]) for s in sorted(got, key=lambda s: -s["gain"]) if s["next"] and s["gain"] > 0]
    if cp:
        lim = min(c for c, _ in cp)
        triggers.insert(0, ("레드라인 해소", round(raw - lim) if raw > lim else 0, cp[0][1].split(" →")[0]))
    return {"score": score, "raw": raw, "band": band(score), "caps": cp, "signals": sigs, "groups": groups,
            "coverage": (len(got), len(sigs)), "drag": [s for s in lost if s["pts"] < s["max"] * 0.5][:3],
            "support": [s for s in good if s["pts"] >= s["max"] * 0.7][:3], "triggers": triggers[:4],
            "split": split(sigs, snap), "tilt": tilt(snap)}


# ─────────────────────────── 한국 vs 미국 · 섹터 쏠림 ───────────────────────────
def split(sigs: list[dict], snap: dict) -> dict:
    """주식 안에서 한국:미국. 한국 쪽(코스피·전닉·외국인·원화)과 미국 쪽(나스닥·S&P·섹터 폭) 점수율 차이로 50:50에서 옮겨요."""
    by = {s["key"]: s for s in sigs if s["pts"] is not None}
    rate = lambda keys: [by[k]["pts"] / by[k]["max"] for k in keys if k in by]
    kr, us = rate(("kospi", "core", "foreign", "krw")), rate(("nasdaq", "spx", "breadth"))
    if not kr or not us:
        return {"kr": 50, "us": 50, "kr_rate": None, "us_rate": None}
    a, b = sum(kr) / len(kr), sum(us) / len(us)
    k = int(min(80, max(20, round((50 + 50 * (a - b)) / 5) * 5)))
    px = snap.get("px", {})
    rel = None
    ks, nq = _ret(_close(px, *KR_IDX), 20), _ret(_close(px, "^IXIC"), 20)
    if ks is not None and nq is not None:
        rel = ks - nq
    return {"kr": k, "us": 100 - k, "kr_rate": a, "us_rate": b, "rel20": rel}


def tilt(snap: dict, n: int = 6) -> dict:
    """추세가 강한/약한 섹터·종목. 미국은 S&P(SPY), 한국은 코스피 대비 20일 상대 등락."""
    px = snap.get("px", {})
    spy, ks = _ret(_close(px, "SPY", "^GSPC"), 20), _ret(_close(px, *KR_IDX), 20)
    rows = []
    us = [(t, nm, "미국") for t, nm in C.SECTORS] + [(t, nm, "미국") for t, nm in C.THEMES if t not in ("SPY", "RSP")]
    kr = [(c, nm, "한국") for c, nm, _ in C.KR_LEADERS]
    for sym, nm, where in us + kr:
        s = _close(px, sym)
        if s is None:
            continue
        v = stage_series(s).iloc[-1]
        d20 = _ret(s, 20)
        if pd.isna(v) or d20 is None:
            continue
        base = spy if where == "미국" else ks
        rel = d20 - (base or 0)
        rows.append({"sym": sym, "name": nm, "where": where, "stage": STAGE_NAME.get(round(float(v), 2), "—"),
                     "pts": float(v), "d20": d20, "rel": rel, "from_high": float((s.iloc[-1] / s.tail(250).max() - 1) * 100)})
    rows.sort(key=lambda r: (r["pts"], r["rel"]), reverse=True)
    strong = [r for r in rows if r["pts"] >= 0.8][:n]
    weak = [r for r in rows[::-1] if r["pts"] <= 0.35][:n]
    return {"strong": strong, "weak": weak, "all": rows}


# ─────────────────────────── 과거 점수(검증용) ───────────────────────────
def history(snap: dict, dgs10: pd.DataFrame | None = None) -> pd.DataFrame:
    """날짜별 점수. 과거 값이 없는 하이일드·외국인 수급은 빼고 계산해요(지금 점수와 조금 다를 수 있어요).
    dgs10: FRED 10년물(date, value). 있으면 야후 ^TNX 대신 써요."""
    px = snap.get("px", {})
    base = {k: _close(px, *v) for k, v in (("nasdaq", ("^IXIC",)), ("spx", ("^GSPC",)), ("kospi", KR_IDX))}
    if base["kospi"] is None and base["nasdaq"] is None:
        return pd.DataFrame()
    idx = sorted(set().union(*[s.index for s in base.values() if s is not None]))
    idx = pd.DatetimeIndex(idx)
    al = lambda s: None if s is None else s.reindex(idx.union(s.index)).ffill(limit=5).reindex(idx)
    parts, mx = {}, {}
    for k, w in (("nasdaq", 10), ("spx", 5), ("kospi", 10)):
        if base[k] is not None:
            parts[k], mx[k] = al(stage_series(base[k])) * w, w
    core = [al(stage_series(s)) for s in (_close(px, c) for c, _ in CORE) if s is not None]
    if core:
        parts["core"], mx["core"] = pd.concat(core, axis=1).mean(axis=1, skipna=False) * 10, 10
    ten = _tnx(px)
    if dgs10 is not None and len(dgs10) > 30:
        d = dgs10.copy()
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        ten = d.drop_duplicates("date", keep="last").set_index("date")["value"].astype(float).sort_index()
    if ten is not None:
        t = al(ten)
        parts["rate"] = pd.Series([np.nan if pd.isna(v) else p_rate(v, None if pd.isna(d) else d)
                                   for v, d in zip(t, t.diff(20))], index=idx)
        mx["rate"] = 15
    oil = _close(px, "CL=F")
    if oil is not None:
        o = al(oil)
        parts["oil"] = pd.Series([np.nan if pd.isna(v) else p_oil(v, None if pd.isna(d) else d)
                                  for v, d in zip(o, o.pct_change(20, fill_method=None) * 100)], index=idx)
        mx["oil"] = 10
    vix = _close(px, "^VIX")
    if vix is not None:
        parts["vix"], mx["vix"] = al(vix).map(lambda v: np.nan if pd.isna(v) else p_vix(v)), 7
    if base["nasdaq"] is not None:
        w = (base["nasdaq"].pct_change() * 100).rolling(5).min()
        parts["panic"], mx["panic"] = al(w).map(lambda v: np.nan if pd.isna(v) else p_panic(v)), 7
    secs = [al(stage_series(s)) for s in (_close(px, t) for t, _ in C.SECTORS) if s is not None]
    if secs:
        m = pd.concat(secs, axis=1)
        share = (m >= 0.55).sum(axis=1) / m.notna().sum(axis=1).replace(0, np.nan)
        parts["breadth"], mx["breadth"] = share.map(lambda v: np.nan if pd.isna(v) else p_breadth(v)), 6
    krw = _close(px, "KRW=X")
    if krw is not None:
        d = al(krw).pct_change(20, fill_method=None) * 100
        parts["krw"], mx["krw"] = d.map(lambda v: np.nan if pd.isna(v) else p_krw(v)), 6
    P = pd.DataFrame(parts, index=idx)
    M = pd.DataFrame({k: np.where(P[k].notna(), mx[k], 0) for k in P}, index=idx)
    total = M.sum(axis=1)
    score = (P.sum(axis=1) / total.replace(0, np.nan) * 100)
    # 레드라인 상한
    if "rate" in P and ten is not None:
        score = score.where(~(al(ten) >= 5), np.minimum(score, 49))
    if "panic" in P:
        score = score.where(~(P["panic"] == 0), np.minimum(score, 64))
    if "core" in P:
        score = score.where(~(P["core"] <= 1.5), np.minimum(score, 64))
    out = pd.DataFrame({"date": idx, "score": score.values})
    for k, s in (("kospi", base["kospi"]), ("nasdaq", base["nasdaq"])):
        if s is not None:
            out[k] = al(s).values
    for k in P:
        out["p_" + k] = P[k].values
    out = out[total.values >= 30].dropna(subset=["score"]).reset_index(drop=True)
    out["band"] = out["score"].map(lambda v: band(v)["name"])
    out.attrs["max"] = mx
    return out


NAMES = {"nasdaq": "나스닥 추세", "spx": "S&P 추세", "kospi": "코스피 추세", "core": "전닉 추세", "rate": "미 10년물",
         "oil": "WTI 유가", "vix": "VIX", "panic": "나스닥 패닉", "breadth": "미국 섹터 폭", "krw": "원/달러"}


def changes(h: pd.DataFrame, back: int = 5) -> dict | None:
    """back 거래일 전과 비교: 점수·구간 변화와 점수가 바뀐 신호."""
    if h.empty or len(h) <= back:
        return None
    now, then = h.iloc[-1], h.iloc[-1 - back]
    moved = []
    for c in [c for c in h.columns if c.startswith("p_")]:
        a, b = then[c], now[c]
        if pd.notna(a) and pd.notna(b) and abs(b - a) >= 0.5:
            moved.append({"key": c[2:], "name": NAMES.get(c[2:], c[2:]), "from": float(a), "to": float(b),
                          "max": h.attrs.get("max", {}).get(c[2:])})
    moved.sort(key=lambda m: -abs(m["to"] - m["from"]))
    d1 = float(now["score"] - h.iloc[-2]["score"]) if len(h) > 1 else None
    return {"d1": d1, "d5": float(now["score"] - then["score"]), "band_then": then["band"], "band_now": now["band"],
            "moved": moved, "date_then": then["date"]}


def band_stats(h: pd.DataFrame, fwd: int = 20) -> list[dict]:
    """점수 구간별로, 그 뒤 20거래일 지수가 평균 얼마나 움직였나."""
    if h.empty:
        return []
    h = h.copy()
    for k in ("kospi", "nasdaq"):
        if k in h:
            h[f"{k}_f"] = (h[k].shift(-fwd) / h[k] - 1) * 100
    rows = []
    for lo, name, eq, col, _ in BANDS:
        g = h[h["band"] == name]
        r = {"band": name, "equity": eq, "color": col, "days": len(g)}
        for k in ("kospi", "nasdaq"):
            f = g.get(f"{k}_f")
            f = f.dropna() if f is not None else pd.Series(dtype=float)
            r[k] = float(f.mean()) if len(f) else None
            r[k + "_win"] = float((f > 0).mean() * 100) if len(f) else None
        rows.append(r)
    return rows
