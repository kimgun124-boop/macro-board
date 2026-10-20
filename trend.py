"""추세추종 기준. 숫자로 계산한 규칙만 있고, 규칙 자체는 knowledge.md(보내 주신 블로그 정리)에서 왔어요.

- 10일선 회복 = 하락이 멈췄는지 보는 첫 기준
- 20일선 = 상승 추세 속 첫 눌림 자리
- 50일선 = 추세의 중심선. 이탈하면 시각이 갈리기 시작
- 200일선 = 주도주 자격 시험('사나이테스트')
- 나스닥 하루 -3% 이상 = 패닉 신호, 미 10년물 5% 이상 = 주식 비중을 크게 줄이는 선(블로그 기준)
"""
from __future__ import annotations

import pandas as pd

import config as C

MAS = (10, 20, 50, 200)


def metrics(df: pd.DataFrame | None) -> dict | None:
    """한 종목·지수의 추세 상태."""
    if df is None or len(df) < 25:
        return None
    c = df["close"].astype(float).reset_index(drop=True)
    last = float(c.iloc[-1])
    ma = {n: float(c.tail(n).mean()) if len(c) >= n else None for n in MAS}
    above = {n: (last > v) if v else None for n, v in ma.items()}
    ma50_prev = float(c.iloc[-60:-10].mean()) if len(c) >= 60 else None
    rising50 = (ma[50] > ma50_prev) if ma[50] and ma50_prev else None
    hi = float(c.tail(250).max())
    gap50 = (last / ma[50] - 1) * 100 if ma[50] else None
    # 최근 3일 안에 10일선을 아래→위로 넘었나
    ma10s = c.rolling(10).mean()
    crossed10 = bool(len(c) > 14 and any(c.iloc[-i] > ma10s.iloc[-i] and c.iloc[-i - 1] <= ma10s.iloc[-i - 1]
                                         for i in range(1, 4)))
    # 거래량 실린 장대음봉(최근 5일): 2% 넘게 빠지고 거래량이 50일 평균의 1.5배 이상
    heavy = False
    if "volume" in df and "open" in df and df["volume"].astype(float).tail(50).mean() > 0:
        d = df.tail(6).astype({"close": float, "open": float, "volume": float})
        vavg = df["volume"].astype(float).tail(50).mean()
        hit = (d["close"] < d["open"]) & (d["close"].pct_change() < -0.02) & (d["volume"] >= 1.5 * vavg)
        heavy = bool(hit.tail(5).any())
    # 변동성(20일 vs 60일, 일간 등락 표준편차)
    r = c.pct_change()
    vol20, vol60 = float(r.tail(20).std() * 100), float(r.tail(60).std() * 100) if len(c) > 60 else None
    stage, comment = _stage(above, rising50, crossed10)
    return {"last": last, "ma": ma, "above": above, "rising50": rising50, "gap50": gap50, "high": hi,
            "from_high": (last / hi - 1) * 100, "crossed10": crossed10, "heavy_down": heavy,
            "vol20": vol20, "vol60": vol60, "stage": stage, "comment": comment,
            "score": sum(1 for v in above.values() if v) + (1 if rising50 else 0)}


def _stage(above: dict, rising50, crossed10) -> tuple[str, str]:
    a10, a20, a50, a200 = (above[n] for n in MAS)
    if a200 is None:          # 200일치가 안 되면 50일선까지만
        a200 = a50
    if a10 and a20 and a50 and a200:
        return "상승 추세", "이평선 위에 모두 올라 있어요(정배열 구간)." + ("" if rising50 else " 다만 50일선 기울기는 아직 평평해요.")
    if a50 and a200 and not a20:
        return "추세 속 눌림", "50·200일선 위에서 쉬는 중. 20일선 회복 여부가 다음 확인점이에요."
    if a50 and a200:
        return "상승 추세", "50일선 위, 10일선만 잠시 아래예요."
    if a200 and not a50:
        return "중기 조정", "50일선(추세 중심선) 아래. 시각이 갈리는 구간이고 200일선 지지가 관건이에요." + \
               (" 최근 10일선을 회복했어요(하락 멈춤 첫 신호)." if crossed10 else "")
    if a50 and not a200:
        return "회복 시도", "50일선은 넘었지만 200일선 아래예요. 200일선 돌파가 추세 전환 확인점."
    return "하락 추세", "50·200일선 모두 아래예요." + (" 다만 최근 10일선을 회복했어요(하락 멈춤 첫 신호)." if crossed10
                                                  else " 최소 10일선 회복부터 확인해야 해요.")


STAGE_COLOR = {"상승 추세": "#D6333B", "추세 속 눌림": "#E0672B", "회복 시도": "#B7791F", "중기 조정": "#1F66C9",
               "하락 추세": "#1B3F7A"}


def rate_regime(sm: dict) -> dict | None:
    """2년물·10년물의 20일 변화로 금리 국면을 나눠요(베어/불 × 스티프닝/플래트닝)."""
    two, ten = sm.get("fred:DGS2"), sm.get("^TNX")
    if not two or not ten or two.get("a20") is None or ten.get("a20") is None:
        return None
    d2, d10 = two["a20"], ten["a20"]
    steep = d10 > d2
    if d2 >= 0 and d10 >= 0:
        name = "베어 스티프닝" if steep else "베어 플래트닝"
    elif d2 <= 0 and d10 <= 0:
        name = "불 스티프닝" if steep else "불 플래트닝"
    else:
        name = "스티프닝" if steep else "플래트닝"
    return {"name": name, "d2": d2, "d10": d10, "past": REGIME_TABLE.get(name)}


# 보내 주신 이미지(버터대디 인용 표)의 금리 국면별 섹터 상대 성과 — 과거 통계 인용, 사실 확인 전
REGIME_TABLE = {
    "베어 플래트닝": "기술 +14.1%, 경기소비재 +2.2%, 나머지 약세",
    "불 스티프닝": "헬스케어 +18.6%, 필수소비재 +11.1%",
    "베어 스티프닝": "에너지 +11.7%, 기술 +8.3%, 금융 +6.6%, 유틸리티·부동산 -18%대",
}


def _line(level: str, text: str) -> dict:
    return {"level": level, "text": text}


def market_view(snap: dict) -> dict:
    """시장 전체를 추세추종 규칙으로 점검. level: good/warn/bad/info."""
    sm, tr, fred = snap["sm"], snap.get("trend", {}), snap.get("fred", {})
    lines, score = [], 0

    def tline(sym, name):
        nonlocal score
        t = tr.get(sym)
        if not t:
            return
        lv = {"상승 추세": "good", "추세 속 눌림": "good", "회복 시도": "warn", "중기 조정": "warn", "하락 추세": "bad"}[t["stage"]]
        score += {"good": 1, "warn": 0, "bad": -1}[lv]
        lines.append(_line(lv, f"{name}: {t['stage']} — {t['comment']} (고점 대비 {t['from_high']:+.1f}%)"))

    tline("^GSPC", "S&P 500")
    tline("^IXIC", "나스닥")
    tline("^KS11", "코스피")
    tline("^KQ11", "코스닥")

    nq = snap.get("prices_tail", {}).get("^IXIC")
    if nq:
        worst = min(nq)
        if worst <= -3:
            score -= 2
            lines.append(_line("bad", f"나스닥 최근 5일 중 하루 {worst:+.1f}% — 패닉 신호(-3%) 발생. 신규 진입보다 손절선 점검"))
        else:
            lines.append(_line("good", f"나스닥 최근 5일 최악 {worst:+.1f}% — 패닉 신호(-3%)는 아직 없어요"))

    ten = fred.get("DGS10") or sm.get("^TNX")
    if ten:
        v = ten["last"]
        if v >= 5:
            score -= 2
            lines.append(_line("bad", f"미 10년물 {v:.2f}% — 5% 레드라인을 넘었어요(블로그 기준: 실적·내러티브와 무관하게 비중 축소)"))
        elif v >= 4.8:
            score -= 1
            lines.append(_line("warn", f"미 10년물 {v:.2f}% — 5% 레드라인에 가까워요"))
        else:
            lines.append(_line("good", f"미 10년물 {v:.2f}% — 5% 레드라인 아래"))

    secs = [tr.get(s) for s, _ in C.SECTORS]
    secs = [t for t in secs if t]
    if secs:
        n50 = sum(1 for t in secs if t["above"][50])
        lv = "good" if n50 >= len(secs) * 0.6 else ("warn" if n50 >= len(secs) * 0.35 else "bad")
        score += {"good": 1, "warn": 0, "bad": -1}[lv]
        lines.append(_line(lv, f"미국 섹터 {n50}/{len(secs)}개가 50일선 위 — 시장의 폭"
                               + ("이 넓어요" if lv == "good" else ("이 좁아지는 중" if lv == "warn" else "이 크게 좁아요"))))
    rsp, spy = sm.get("RSP"), sm.get("SPY")
    if rsp and spy and rsp["d20"] is not None and spy["d20"] is not None:
        g = rsp["d20"] - spy["d20"]
        lines.append(_line("good" if g >= 0 else "info",
                           f"동일가중−시총가중 20일 {g:+.1f}%p — " + ("중소형주까지 오름세가 퍼졌어요" if g >= 0 else "소수 대형주가 지수를 끌고 있어요")))

    # 주도주가 가장 약한 종목이 되고 있나(미너비니)
    lead = [tr.get(t) for v in C.LEADERS.values() for t, _ in v]
    lead = [t for t in lead if t]
    if lead:
        weak = sum(1 for t in lead if not t["above"][50])
        if weak >= len(lead) * 0.5:
            score -= 1
            lines.append(_line("bad", f"섹터 대장주 {weak}/{len(lead)}개가 50일선 아래 — 주도주 약화(시장 압력 확산 초기 신호, 미너비니)"))
        else:
            lines.append(_line("good", f"섹터 대장주 {len(lead) - weak}/{len(lead)}개가 50일선 위 — 주도주는 버티는 중"))
    big = [(n, tr.get(t)) for t, n in (("MAGS", "M7"), ("AAPL", "애플"), ("MSFT", "MS"), ("GOOGL", "알파벳"))]
    near = [n for n, t in big if t and t["from_high"] >= -3]
    if near:
        lines.append(_line("info", f"{', '.join(near)} 신고가 3% 이내 — 대형주가 신고가 근처면 매크로보다 섹터 문제일 가능성(블로그 관점)"))

    vix = sm.get("^VIX")
    if vix:
        v = vix["last"]
        lv = "bad" if v >= 30 else ("warn" if v >= 20 else "good")
        score += {"good": 0, "warn": 0, "bad": -1}[lv]
        lines.append(_line(lv, f"VIX {v:.1f} — " + ("공포 구간" if v >= 30 else ("불안이 큰 편" if v >= 20 else "평온한 편"))))
    hy = fred.get("BAMLH0A0HYM2")
    if hy and hy.get("a20") is not None:
        lv = "bad" if hy["a20"] >= 0.5 else ("warn" if hy["a20"] >= 0.2 else "good")
        score += {"good": 0, "warn": 0, "bad": -1}[lv]
        lines.append(_line(lv, f"하이일드 스프레드 {hy['last']:.2f}% (20일 {hy['a20']:+.2f}%p) — "
                               + ("신용 위험이 빠르게 커지는 중" if lv == "bad" else ("조금 넓어지는 중" if lv == "warn" else "신용 시장은 안정적"))))

    core = [(n, tr.get(c)) for c, n in (("005930", "삼성전자"), ("000660", "SK하이닉스"))]
    for n, t in core:
        if t and t["vol60"]:
            calm = t["vol20"] < t["vol60"]
            lines.append(_line("good" if calm else "warn",
                               f"{n}: {t['stage']}, 20일 변동성 {t['vol20']:.1f}% vs 60일 {t['vol60']:.1f}% — "
                               + ("변동성 축소 중(블로그: 전닉 변동성 축소가 모든 섹터 반등의 첫 신호)" if calm else "변동성 확대 중")))
        if t and t["heavy_down"]:
            lines.append(_line("warn", f"{n}: 최근 거래량 실린 장대음봉 — 단기 고점 신호로 보는 경우가 많아요"))

    if score >= 3:
        verdict, tone = "들어가기 괜찮은 구간", "good"
        say = "지수가 이평선 위에 있고 위험 신호가 적어요. 추세추종으로는 주도 섹터 위주로 비중을 늘리는 구간이에요."
    elif score >= 1:
        verdict, tone = "선별적으로", "warn"
        say = "추세는 살아 있지만 경고등이 몇 개 켜져 있어요. 50일선 위에 있는 강한 섹터만 고르고, 나머지는 기다리는 쪽이 규칙에 맞아요."
    elif score >= -1:
        verdict, tone = "기다리기", "warn"
        say = "추세가 갈리는 구간이에요. 최소 10일선 회복(하락 멈춤)과 50일선 회복을 확인하고 들어가는 게 규칙이에요."
    else:
        verdict, tone = "방어", "bad"
        say = "하락 추세나 위험 신호가 많아요. 신규 매수를 줄이고 손절선을 올리는 구간이에요. 반등이 나와도 새 주도주인지(반전), 예전 주도주인지(반등) 구분해 보세요."
    return {"verdict": verdict, "tone": tone, "say": say, "score": score, "lines": lines}
