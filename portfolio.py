"""내 계좌 점검. 보유 종목과 비중을 적으면 종목마다 추세·점검선·금리/유가 민감도를 계산하고,
계좌 전체를 비중 판단(alloc.py)의 권장 주식 비중과 비교해요. 숫자는 모두 과거 시세로 계산한 사실이에요.

입력 한 줄에 하나: '삼성전자 30', '000660 20', 'NVDA 10', '현금 40' (비중은 %, 합이 100이 아니면 나머지는 현금)
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

import alloc
import config as C
import sources as S

# 이름 → 종목코드(한국) 또는 야후 티커. 목록에 없으면 6자리 코드나 미국 티커를 그대로 적으면 돼요.
NAMES = {n: c for c, n, _ in C.KR_LEADERS} | {
    "삼성전기": "009150", "SK스퀘어": "402340", "한미반도체": "042700", "LS ELECTRIC": "010120", "LS일렉트릭": "010120",
    "효성중공업": "298040", "삼성E&A": "028050", "현대로템": "064350", "HD한국조선해양": "009540", "한국전력": "015760",
    "에코프로": "086520", "에코프로비엠": "247540", "알테오젠": "196170", "NAVER": "035420", "네이버": "035420",
    "카카오": "035720", "셀트리온": "068270", "기아": "000270", "POSCO홀딩스": "005490", "LG전자": "066570",
    "KODEX 200": "069500", "KODEX 레버리지": "122630", "KODEX 반도체": "091160", "TIGER 미국S&P500": "360750",
    "한화에어로": "012450", "하이닉스": "000660", "삼전": "005930", "두산에너빌": "034020", "HD현대일렉": "267260",
} | {n: t for v in C.LEADERS.values() for t, n in v}
CASH = re.compile(r"^(현금|예수금|cash|달러|원화|MMF|CMA)$", re.I)
EXAMPLE = "삼성전자 30\nSK하이닉스 20\n현금 50"


def parse(text: str) -> tuple[list[dict], float, list[str]]:
    """→ (보유 [{name, code, kr, w}], 현금 %, 못 알아본 줄)."""
    rows, cash, bad = [], 0.0, []
    for line in (text or "").splitlines():
        line = line.strip().replace("%", "")
        if not line:
            continue
        m = re.match(r"^(.*?)[\s,:=]+([\d.]+)$", line)
        if not m:
            bad.append(line)
            continue
        name, w = m.group(1).strip(), float(m.group(2))
        if CASH.match(name):
            cash += w
            continue
        code = NAMES.get(name) or NAMES.get(name.upper()) or name.upper()
        kr = bool(re.fullmatch(r"\d{6}", code))
        if not kr and not re.fullmatch(r"[A-Z0-9.^=\-]{1,12}", code):
            bad.append(line)
            continue
        label = name if name != code else next((n for n, c in NAMES.items() if c == code), code)
        rows.append({"name": label, "code": code, "kr": kr, "w": w})
    total = sum(r["w"] for r in rows) + cash
    if total > 0 and abs(total - 100) > 0.5:
        if total < 100:
            cash += 100 - total
        else:
            k = 100 / total
            for r in rows:
                r["w"] *= k
            cash *= k
    return rows, cash, bad


def encode(text: str) -> str:
    """주소창에 넣을 짧은 문자열(즐겨찾기하면 다음에도 그대로)."""
    rows, cash, _ = parse(text)
    parts = [f'{r["name"]}:{r["w"]:g}' for r in rows] + ([f"현금:{cash:g}"] if cash else [])
    return ",".join(parts)


def decode(q: str) -> str:
    return "\n".join(p.replace(":", " ") for p in (q or "").split(",") if p)


def _series(df: pd.DataFrame | None) -> pd.Series | None:
    if df is None or len(df) < 30:
        return None
    d = df[["date", "close"]].copy()
    d["date"] = S.day(d["date"])
    return d.drop_duplicates("date", keep="last").set_index("date")["close"].astype(float).sort_index()


def _beta(ret: pd.Series, factor: pd.Series, kr: bool) -> tuple[float | None, int]:
    """종목 일간 등락(%)을 요인 변화에 회귀한 기울기. 한국 종목은 '전날 밤 미국' 요인에 맞춰요."""
    a = ret.dropna().rename("y").reset_index()
    b = factor.dropna().rename("x").reset_index()
    a.columns, b.columns = ["date", "y"], ["bdate", "x"]
    a["date"], b["bdate"] = S.day(a["date"]), S.day(b["bdate"])      # 출처마다 다른 날짜 단위를 맞춰야 merge_asof가 돼요
    if a.empty or b.empty:
        return None, 0
    m = pd.merge_asof(a.sort_values("date"), b.sort_values("bdate"), left_on="date", right_on="bdate",
                      allow_exact_matches=not kr, direction="backward")
    m = m[(m["date"] - m["bdate"]).dt.days <= 4].dropna().tail(250)
    if len(m) < 60 or m["x"].var() == 0:
        return None, len(m)
    return float(np.cov(m["x"], m["y"])[0, 1] / m["x"].var()), len(m)


def check(rows: list[dict], cash: float, px: dict, snap: dict, a: dict) -> dict:
    """px = {code: 일봉}. a = alloc.build 결과."""
    ten = alloc._tnx(snap.get("px", {}))
    oil = alloc._close(snap.get("px", {}), "CL=F")
    f_rate = ten.diff() * 100 if ten is not None else None          # bp
    f_oil = oil.pct_change() * 100 if oil is not None else None      # %
    kospi, nq = alloc._close(snap.get("px", {}), *alloc.KR_IDX), alloc._close(snap.get("px", {}), "^IXIC")
    out = []
    for r in rows:
        s = _series(px.get(r["code"]))
        item = {**r, "ok": s is not None}
        if s is None:
            out.append(item)
            continue
        st = alloc.stage_series(s)
        v = st.iloc[-1]
        stage = alloc.STAGE_NAME.get(round(float(v), 2), "—") if not pd.isna(v) else "—"
        ma = {n: float(s.tail(n).mean()) if len(s) >= n else None for n in (10, 20, 50, 200)}
        last = float(s.iloc[-1])
        ret = s.pct_change() * 100
        br, nr = _beta(ret, f_rate, r["kr"]) if f_rate is not None else (None, 0)
        bo, _ = _beta(ret, f_oil, r["kr"]) if f_oil is not None else (None, 0)
        bench = kospi if r["kr"] else nq
        corr = None
        if bench is not None:
            j = pd.concat([ret, bench.pct_change() * 100], axis=1, join="inner").dropna().tail(250)
            corr = float(j.corr().iloc[0, 1]) if len(j) > 60 else None
        # 점검선(블로그 규칙): 50일선 위면 50일선, 아래면 10일선 회복 여부
        if v is not None and not pd.isna(v) and v >= 0.55:
            line, line_name = ma[50], "50일선(추세 중심선)"
        else:
            line, line_name = ma[10], "10일선(하락 멈춤 확인)"
        rule = {"상승 추세": "보유 · 20일선 눌림이 추가 후보 자리", "추세 속 눌림": "보유 · 50일선 지지 확인",
                "회복 시도": "200일선 돌파 확인 전 비중 유지", "중기 조정(10일선 회복)": "하락 멈춤 첫 신호 · 50일선 회복 확인",
                "중기 조정": "50일선 아래 · 반등 시 비중 줄이기 후보", "하락 추세(10일선 회복)": "10일선은 회복 · 50일선까지 확인",
                "하락 추세": "신규 매수 멈춤 · 10일선 회복 전까지 기다리기"}.get(stage, "")
        item.update({"last": last, "d1": float(ret.iloc[-1]), "d20": float((last / s.iloc[-21] - 1) * 100) if len(s) > 21 else None,
                     "stage": stage, "pts": None if pd.isna(v) else float(v), "from_high": float((last / s.tail(250).max() - 1) * 100),
                     "line": line, "line_name": line_name, "line_gap": (last / line - 1) * 100 if line else None,
                     "vol": float(ret.tail(20).std()), "beta_rate": br, "beta_oil": bo, "corr": corr, "rule": rule,
                     "series": s})
        out.append(item)
    eq = sum(r["w"] for r in rows)
    got = [r for r in out if r["ok"]]
    wsum = sum(r["w"] for r in got) or 1
    wavg = lambda k: (sum(r["w"] * r[k] for r in got if r.get(k) is not None) / wsum) if got else None
    band = a["band"]
    lo, hi = [int(x) for x in band["equity"].rstrip("%").split("~")]
    gap = 0 if lo <= eq <= hi else (eq - hi if eq > hi else eq - lo)
    kr_w = sum(r["w"] for r in rows if r["kr"])
    semi = sum(r["w"] for r in rows if r["code"] in ("005930", "000660", "042700", "091160", "NVDA", "TSM", "AVGO", "MU", "AMD", "SMH"))
    down = sum(r["w"] for r in got if r.get("pts") is not None and r["pts"] <= 0.35)
    up = sum(r["w"] for r in got if r.get("pts") is not None and r["pts"] >= 0.8)
    port_20 = wavg("d20")
    return {"items": out, "equity": eq, "cash": cash, "band": band, "lo": lo, "hi": hi, "gap": gap,
            "kr_w": kr_w, "us_w": eq - kr_w, "semi": semi, "down_w": down, "up_w": up,
            "beta_rate": wavg("beta_rate"), "beta_oil": wavg("beta_oil"), "vol": wavg("vol"),
            "port_d20": None if port_20 is None else port_20 * eq / 100, "split": a["split"]}


def notes(c: dict) -> list[tuple[str, str]]:
    """계좌 전체 한 줄 점검(규칙 결과). (level, 문장) · level: good/warn/bad."""
    out = []
    if c["gap"] > 0:
        out.append(("bad", f'주식 {c["equity"]:.0f}%로 권장({c["band"]["name"]} {c["band"]["equity"]})보다 {c["gap"]:.0f}%p 많아요.'))
    elif c["gap"] < 0:
        out.append(("warn", f'주식 {c["equity"]:.0f}%로 권장({c["band"]["name"]} {c["band"]["equity"]})보다 {-c["gap"]:.0f}%p 적어요.'))
    else:
        out.append(("good", f'주식 {c["equity"]:.0f}%는 권장({c["band"]["name"]} {c["band"]["equity"]}) 안이에요.'))
    if c["equity"]:
        if c["down_w"] >= c["equity"] * 0.4:
            out.append(("bad", f'하락 추세·중기 조정 종목에 {c["down_w"]:.0f}%가 실려 있어요(블로그: 약한 종목부터 줄이기).'))
        if c["semi"] >= c["equity"] * 0.6:
            out.append(("warn", f'반도체에 주식의 {c["semi"] / c["equity"] * 100:.0f}%가 몰려 있어요(10월 외국인 매도가 집중된 곳).'))
        kr_share = c["kr_w"] / c["equity"] * 100
        want = c["split"]["kr"]
        if abs(kr_share - want) >= 20:
            out.append(("warn", f'주식 안에서 한국 {kr_share:.0f}% · 미국 {100 - kr_share:.0f}%. 신호로 본 나눔은 한국 {want}% · 미국 {100 - want}%.'))
    if c["beta_rate"] is not None:
        hit = c["beta_rate"] * 10 * c["equity"] / 100
        out.append(("warn" if hit < -0.3 else "good",
                    f'과거 1년 기준, 미 10년물이 10bp 오르는 날 계좌는 평균 {hit:+.2f}% 움직였어요.'))
    if c["beta_oil"] is not None:
        hit = c["beta_oil"] * 5 * c["equity"] / 100
        out.append(("warn" if hit < -0.3 else "good", f'유가가 5% 오르는 날 계좌는 평균 {hit:+.2f}% 움직였어요.'))
    return out
