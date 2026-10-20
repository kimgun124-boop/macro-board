"""화면 그리기. 데이터는 macro.py, 이 파일은 그리기만. 탭마다 함수 하나예요."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import ai
import charts
import config as C
import econ
import issues
import macro
import sources as S
import trend

UP, DOWN, FLAT = "#D6333B", "#1F66C9", "#51616C"     # 한국식: 상승 빨강, 하락 파랑
CHIP = {"교차확인": "#1D7A4C", "단일출처": "#51616C", "상충": "#B7791F", "주장": "#C53030", "의견": "#7B5EA7", "없음": "#9AA5AE"}

CSS = """
<style>
.mc-sum{background:#fff;border:1px solid #DCE3E7;border-radius:10px;padding:12px 14px;margin:4px 0 14px;line-height:1.7}
.mc-sum b{font-weight:600}
.mc-wrap{overflow-x:auto;margin-bottom:6px}
.mc-t{width:100%;border-collapse:collapse;font-size:.88rem;font-variant-numeric:tabular-nums}
.mc-t th{color:#51616C;font-weight:500;text-align:right;padding:5px 8px;border-bottom:1px solid #DCE3E7;white-space:nowrap}
.mc-t td{text-align:right;padding:5px 8px;border-bottom:1px solid #EEF2F4;white-space:nowrap}
.mc-t .l{text-align:left}
.mc-t .note{color:#6B7A85;font-size:.78rem;white-space:normal;min-width:12rem;text-align:left}
.mc-chip{display:inline-block;padding:0 8px;border-radius:999px;border:1px solid;font-size:.75rem;line-height:1.6}
.mc-legend{font-size:.8rem;color:#51616C;margin:-4px 0 10px}
.mc-news{border:1px solid #DCE3E7;border-radius:10px;padding:10px 12px;margin-bottom:8px;background:#fff}
.mc-news .h{font-weight:600;margin:4px 0}
.mc-news .m{font-size:.78rem;color:#6B7A85}
.mc-news a{color:inherit}
.mc-bar{display:grid;grid-template-columns:minmax(7rem,max-content) 1fr 4.5rem;gap:4px 8px;align-items:center;font-size:.85rem}
.mc-bar .track{position:relative;height:14px}
.mc-bar .mid{position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #C9D3D9}
.mc-bar .fill{position:absolute;top:2px;bottom:2px;border-radius:3px}
.mc-bar .v{text-align:right;font-variant-numeric:tabular-nums}
</style>
"""


def _c(v) -> str:
    if v is None or pd.isna(v) or v == 0:
        return FLAT
    return UP if v > 0 else DOWN


def _p(v, d=2) -> str:
    return "—" if v is None or pd.isna(v) else f'<span style="color:{_c(v)}">{v:+.{d}f}%</span>'


def _pp(v) -> str:
    return "—" if v is None or pd.isna(v) else f'<span style="color:{_c(v)}">{v:+.3f}%p</span>'


def _chip(status: str) -> str:
    col = CHIP.get(status, FLAT)
    return f'<span class="mc-chip" style="color:{col};border-color:{col}">{html.escape(status)}</span>'


def _ma(s) -> str:
    if not s or s.get("above50") is None:
        return "—"
    return '<span style="color:%s">%s</span>' % ((UP, "위") if s["above50"] else (DOWN, "아래"))


def _table(head: list[str], rows: list[list[str]], left: int = 1) -> str:
    th = "".join(f'<th class="{"l" if i < left else ""}">{h}</th>' for i, h in enumerate(head))
    body = "".join("<tr>" + "".join(f'<td class="{"l" if i < left else ("note" if c.startswith("§") else "")}">{c.lstrip("§")}</td>'
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="mc-wrap"><table class="mc-t"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _bars(items: list[tuple[str, float | None]]) -> str:
    items = [(n, v) for n, v in items if v is not None and not pd.isna(v)]
    if not items:
        return '<div class="mc-legend">불러오지 못했어요</div>'
    ext = max(abs(v) for _, v in items) or 1
    rows = []
    for n, v in sorted(items, key=lambda x: -x[1]):
        w = abs(v) / ext * 50
        left = 50 if v >= 0 else 50 - w
        rows.append(f'<div>{html.escape(n)}</div><div class="track"><div class="mid"></div>'
                    f'<div class="fill" style="left:{left:.1f}%;width:{max(w, .5):.1f}%;background:{_c(v)}"></div></div>'
                    f'<div class="v">{_p(v)}</div>')
    return '<div class="mc-bar">' + "".join(rows) + "</div>"


def header(snap: dict) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    lines = macro.facts(snap)
    st.markdown(f'<div class="mc-sum"><b>숫자로 본 오늘</b> ({snap["at"]:%m/%d %H:%M} 기준)<br>'
                + " · ".join(html.escape(x) for x in lines) + "</div>", unsafe_allow_html=True)
    st.markdown('<div class="mc-legend">검증: ' + " ".join(_chip(k) for k in ("교차확인", "단일출처", "상충")) +
                f" — 야후 종가를 stooq·네이버·FRED와 같은 날짜끼리 맞춰 봐요(차이 {C.TOL}% 안이면 교차확인). "
                "시세는 15분 안팎 지연이에요.</div>", unsafe_allow_html=True)


def period_pick() -> tuple[str, str]:
    period = st.radio("기간", ["1일", "5일", "20일"], horizontal=True, key="mc_period")
    return period, {"1일": "d1", "5일": "d5", "20일": "d20"}[period]


def tab_markets(snap: dict) -> None:
    sm, ver, fred = snap["sm"], snap["ver"], snap["fred"]
    st.markdown("#### 세계 주요 지수")
    rows = []
    for i in C.INDICES:
        s = sm.get(i["yf"])
        v, note = ver.get(i["yf"], ("없음", ""))
        rows.append([i["region"], i["name"], f'{s["last"]:,.2f}' if s else "—", _p(s and s["d1"]), _p(s and s["d5"]),
                     _p(s and s["d20"]), _ma(s), f'{s["date"]:%m/%d}' if s else "—", _chip(v), "§" + html.escape(note)])
    st.markdown(_table(["지역", "지수", "종가", "1일", "5일", "20일", "50일선", "기준일", "검증", "대조"], rows, left=2),
                unsafe_allow_html=True)

    st.markdown("#### 금리 · 환율 · 원자재")
    rows = []
    for m in C.MACRO:
        key = macro.key_of(m)
        s = sm.get(key)
        v, note = ver.get(key, ("없음", ""))
        if m["kind"] == "rate":
            val, d1, d20 = (f'{s["last"]:.3f}%' if s else "—"), _pp(s and s.get("a1")), _pp(s and s.get("a20"))
        else:
            val = f'{m.get("unit", "")}{s["last"]:,.2f}' if s else "—"
            d1, d20 = _p(s and s["d1"]), _p(s and s["d20"])
        rows.append([m["group"], m["name"], val, d1, d20, f'{s["date"]:%m/%d}' if s else "—", _chip(v), "§" + html.escape(note)])
    st.markdown(_table(["구분", "항목", "값", "1일", "20일", "기준일", "검증", "대조"], rows, left=2), unsafe_allow_html=True)

    st.markdown("#### 시장 체력 · 위험 지표")
    rows = []
    for x in C.VOL:
        s = sm.get(x["yf"])
        rows.append(["변동성", x["name"], f'{s["last"]:.2f}' if s else "—", _p(s and s["d1"]), _p(s and s["d20"]),
                     f'{s["date"]:%m/%d}' if s else "—", "§" + x["read"]])
    for f in C.FRED:
        s = fred.get(f["id"])
        rows.append([f["group"], f["name"], f'{s["last"]:.2f}%' if s else "—", _pp(s and s["a1"]), _pp(s and s.get("a20")),
                     f'{s["date"]:%m/%d}' if s else "—", "§" + f["read"] + " (FRED)"])
    rsp, spy = sm.get("RSP"), sm.get("SPY")
    if rsp and spy and rsp["d20"] is not None and spy["d20"] is not None:
        rows.append(["시장 폭", "동일가중 − 시총가중 (20일)", f'{rsp["d20"] - spy["d20"]:+.2f}%p', _p(rsp["d1"]), _p(rsp["d20"]),
                     f'{rsp["date"]:%m/%d}', "§음수면 소수 대형주가 지수를 끌고 가는 중. 1일·20일은 RSP 등락"])
    st.markdown(_table(["구분", "지표", "값", "1일", "20일", "기준일", "읽는 법"], rows, left=2), unsafe_allow_html=True)


def tab_sectors(snap: dict) -> None:
    sm, ver = snap["sm"], snap["ver"]
    period, k = period_pick()
    st.markdown("#### 미국 섹터 ETF")
    sec = dict(C.SECTORS)
    st.markdown(_bars([(f"{n} {s}", (sm.get(s) or {}).get(k)) for s, n in C.SECTORS]), unsafe_allow_html=True)

    st.markdown("#### 섹터별 대장주")
    st.caption("섹터 대비 = 종목 등락 − 소속 섹터 ETF 등락(같은 기간). 양수면 섹터보다 강했다는 뜻이에요.")
    rows = []
    for etf, names in C.LEADERS.items():
        es = sm.get(etf)
        for t, n in names:
            s = sm.get(t)
            rel = s[k] - es[k] if s and es and s[k] is not None and es[k] is not None else None
            v, _ = ver.get(t, ("없음", ""))
            rows.append([f"{sec[etf]} {etf}", t, n, f'{s["last"]:,.2f}' if s else "—", _p(s and s[k]),
                         "—" if rel is None else f'<span style="color:{_c(rel)}">{rel:+.2f}%p</span>', _ma(s), _chip(v)])
    st.markdown(_table(["섹터", "티커", "종목", "종가($)", period, "섹터 대비", "50일선", "검증"], rows, left=3),
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 테마 ETF")
        st.markdown(_bars([(f"{n} {s}", (sm.get(s) or {}).get(k)) for s, n in C.THEMES]), unsafe_allow_html=True)
    with c2:
        st.markdown("#### 한국 대장주")
        st.markdown(_bars([(n, (sm.get(c) or {}).get(k)) for c, n, _ in C.KR_LEADERS]), unsafe_allow_html=True)
        st.caption("네이버 일봉(장중 갱신). 단일출처예요.")


def tab_news(snap: dict) -> None:
    news = snap.get("news") or []
    pick = st.radio("보기", ["사실만(교차확인·단일출처)", "교차확인만", "주장·의견까지 전부"], horizontal=True, key="mc_news")
    allow = {"사실만(교차확인·단일출처)": ("교차확인", "단일출처"), "교차확인만": ("교차확인",),
             "주장·의견까지 전부": ("교차확인", "단일출처", "주장", "의견")}[pick]
    cnt = {s: sum(1 for n in news if n["status"] == s) for s in CHIP}
    st.caption(f"지난 24시간 {len(news)}건 · 교차확인 {cnt['교차확인']} · 단일출처 {cnt['단일출처']} · "
               f"주장 {cnt['주장']} · 의견(전망·추측·질문형 제목) {cnt['의견']}. "
               "교차확인 = 서로 다른 언론사 2곳 이상이 같은 사건을 보도. 제목 기준 자동 분류라 원문을 꼭 확인하세요.")
    shown = [n for n in news if n["status"] in allow][:40]
    if not shown:
        st.caption("조건에 맞는 뉴스가 없어요.")
    for n in shown:
        when = n["when"].astimezone(S.KST).strftime("%m/%d %H:%M") if n["when"] else ""
        others = "".join(f' · <a href="{html.escape(o["url"])}" target="_blank">{html.escape(o["source"])}</a>'
                         for o in n["others"])
        st.markdown(
            f'<div class="mc-news">{_chip(n["status"])} <span class="m">{when}</span>'
            f'<div class="h"><a href="{html.escape(n["url"])}" target="_blank">{html.escape(n["title"])}</a></div>'
            f'<div class="m">{html.escape(", ".join(n["sources"]))}{others}</div></div>',
            unsafe_allow_html=True)


# ═══════════════════════════ 오늘의 판단(추세추종 + AI) ═══════════════════════════
LEVEL = {"good": ("●", UP), "warn": ("●", "#B7791F"), "bad": ("●", DOWN), "info": ("●", FLAT)}
TONE_BG = {"good": "#FDECEC", "warn": "#FFF6E5", "bad": "#E8F0FB"}


@st.cache_data(ttl=3600, show_spinner=False, max_entries=30)
def _ai(context: str, question: str) -> dict:
    return ai.ask(context, question)


def _ai_block(key: str, context: str, question: str, label: str) -> None:
    """버튼을 눌러야 AI를 불러요(비용 때문에). 결과는 1시간 보관."""
    if not ai.api_key():
        st.info("AI 해설을 쓰려면 Streamlit 앱 설정 → Secrets에 `ANTHROPIC_API_KEY = \"sk-ant-...\"` 한 줄을 넣어 주세요.")
        return
    if st.button(label, key=f"ai_btn_{key}", type="primary"):
        with st.spinner("AI가 외신·리포트를 찾아 사실을 확인하는 중이에요(1~2분)…"):
            st.session_state[f"ai_{key}"] = _ai(context, question)
    res = st.session_state.get(f"ai_{key}")
    if not res:
        return
    if res["error"]:
        st.warning(res["error"])
        return
    st.markdown(res["text"])
    if res["sources"]:
        st.markdown("**AI가 확인한 출처**<br>" + "<br>".join(
            f'· <a href="{html.escape(u)}" target="_blank">{html.escape(t)}</a>' for u, t in res["sources"][:15]),
            unsafe_allow_html=True)
    st.caption("AI 해설은 해석이에요. '사실'로 표시된 것도 링크 원문을 꼭 확인하세요. 투자 권유가 아니에요.")


def tab_today(snap: dict) -> None:
    v = trend.market_view(snap)
    st.markdown(
        f'<div class="mc-sum" style="background:{TONE_BG[v["tone"]]}"><b style="font-size:1.15rem">추세추종 판단: {v["verdict"]}</b>'
        f'<br>{html.escape(v["say"])}</div>', unsafe_allow_html=True)
    st.markdown("".join(
        f'<div style="margin:2px 0"><span style="color:{LEVEL[x["level"]][1]}">{LEVEL[x["level"]][0]}</span> '
        f'{html.escape(x["text"])}</div>' for x in v["lines"]), unsafe_allow_html=True)
    st.caption("빨강 = 좋은 신호, 노랑 = 주의, 파랑 = 나쁜 신호, 회색 = 참고. 규칙은 보내 주신 블로그(버터대디·미너비니 등)의 "
               "추세추종 기준을 숫자로 옮긴 거예요(10일선 회복, 50일선 중심선, 200일선 사나이테스트, 나스닥 -3%, 10년물 5%). "
               "판단 문구는 규칙의 결과일 뿐 투자 권유가 아니에요.")

    reg = trend.rate_regime(snap["sm"])
    if reg:
        st.markdown("#### 금리 국면")
        secs = sorted([(n, snap["sm"][s]["d20"]) for s, n in C.SECTORS if snap["sm"].get(s) and snap["sm"][s]["d20"] is not None],
                      key=lambda x: -x[1])
        now = " · ".join(f"{n} {d:+.1f}%" for n, d in secs[:3]) + "  …  " + " · ".join(f"{n} {d:+.1f}%" for n, d in secs[-3:])
        st.markdown(
            f'<div class="mc-sum"><b>{reg["name"]}</b> — 20일 동안 2년물 {reg["d2"]:+.2f}%p, 10년물 {reg["d10"]:+.2f}%p<br>'
            f'과거 이 국면에서 강했던 섹터(블로그 인용 표): {html.escape(reg["past"] or "표에 없는 국면이에요")}<br>'
            f'최근 20일 실제 섹터: 강한 쪽 {html.escape(now)}</div>', unsafe_allow_html=True)

    st.markdown("#### 🤖 AI 시황 해설")
    st.caption("대시보드 숫자 + 뉴스 + 보내 주신 이미지에서 정리한 지식 노트를 주고, 외신(NYT·WSJ·FT·Reuters·Bloomberg 등)을 "
               "직접 검색해 사실을 확인한 뒤 이슈와 섹터 반응을 연결해 설명하게 해요.")
    _ai_block("market", ai.market_context(snap, v, issues.build(snap), reg), ai.MARKET_ASK, "AI 해설 만들기")


# ═══════════════════════════ 차트 보드 ═══════════════════════════
def _groups() -> dict[str, list[tuple[str, str]]]:
    return {
        "세계 지수": [(i["yf"], i["name"]) for i in C.INDICES],
        "미국 섹터 ETF": [(s, f"{n}") for s, n in C.SECTORS],
        "테마 ETF": [(s, n) for s, n in C.THEMES],
        "섹터 대장주": [(t, n) for v in C.LEADERS.values() for t, n in v],
        "한국 대장주": [(c, n) for c, n, _ in C.KR_LEADERS],
    }


def _fmt_for(last: float) -> str:
    return ",.0f" if last >= 1000 else ",.2f"


def tab_charts(snap: dict) -> None:
    px, tr, sm = snap.get("px", {}), snap.get("trend", {}), snap["sm"]
    groups = _groups()
    c1, c2 = st.columns([3, 2])
    g = c1.radio("묶음", list(groups), horizontal=True, key="ch_group")
    order = c2.radio("정렬", ["기본", "20일 강한 순", "추세 점수 순"], horizontal=True, key="ch_order")
    items = [(s, n) for s, n in groups[g] if s in px]
    if order == "20일 강한 순":
        items.sort(key=lambda x: -((sm.get(x[0]) or {}).get("d20") or -999))
    elif order == "추세 점수 순":
        items.sort(key=lambda x: -((tr.get(x[0]) or {}).get("score") or -1))
    if not items:
        st.info("차트 데이터를 받지 못했어요.")
        return
    st.caption("작은 차트: 최근 6개월 일봉 · 초록 20일선 · 보라 50일선 · 회색 200일선. 추세 단계는 이평선 위치로 자동 판정해요.")
    cols = st.columns(3)
    for i, (sym, name) in enumerate(items):
        s, t = sm.get(sym), tr.get(sym)
        with cols[i % 3]:
            stage = t["stage"] if t else "—"
            col = trend.STAGE_COLOR.get(stage, FLAT)
            last = f'{s["last"]:{_fmt_for(s["last"])}}' if s else "—"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:6px">'
                f'<b>{html.escape(name)} <span style="color:#6B7A85;font-weight:400;font-size:.8rem">{html.escape(sym)}</span></b>'
                f'<span>{last} {_p(s and s["d1"])}</span></div>'
                f'<div style="font-size:.78rem;margin-bottom:-6px">'
                f'<span class="mc-chip" style="color:{col};border-color:{col}">{stage}</span> '
                f'20일 {_p(s and s["d20"], 1)} · 고점 대비 {_p(t and t["from_high"], 1)}</div>',
                unsafe_allow_html=True)
            st.plotly_chart(charts.mini(px[sym]), key=f"mini_{g}_{sym}", config={"displayModeBar": False, "staticPlot": True})
            if t:
                st.markdown(f'<div style="font-size:.78rem;color:#51616C;margin:-10px 0 8px">{html.escape(t["comment"])}</div>',
                            unsafe_allow_html=True)

    st.markdown("#### 크게 보기")
    d1, d2 = st.columns([3, 2])
    pick = d1.selectbox("종목·지수", items, format_func=lambda x: f"{x[1]} ({x[0]})", key=f"ch_pick_{g}")
    per = d2.radio("기간", list(charts.PERIODS), index=1, horizontal=True, key="ch_per")
    df = px.get(pick[0])
    if df is not None and len(df):
        st.plotly_chart(charts.candle(df, charts.PERIODS[per], fmt=_fmt_for(float(df["close"].iloc[-1]))),
                        key="big_chart", config={"displaylogo": False, "scrollZoom": True})
        t = tr.get(pick[0])
        if t:
            ma = " · ".join(f"{k}일선 {'위' if t['above'][k] else '아래'}" for k in trend.MAS if t["above"][k] is not None)
            st.caption(f"{t['stage']}: {t['comment']} ({ma}, 50일선 이격 {t['gap50']:+.1f}%)")


# ═══════════════════════════ 이슈 ↔ 섹터 ═══════════════════════════
def tab_issues(snap: dict) -> None:
    st.caption("뉴스 제목으로 이슈를 찾고, 그 이슈를 보여 주는 지표가 5거래일 동안 움직인 방향과 관련 섹터가 실제로 "
               "같은 쪽으로 움직였는지 맞춰 봐요. '가설'은 보내 주신 블로그·리포트에서 나온 연결고리예요. "
               "주요 외신 = Reuters·Bloomberg·NYT·WSJ·FT·Economist·AP·CNBC 등.")
    for x in issues.build(snap):
        n = len(x["news"])
        badge = f'뉴스 {n}건 · 교차확인 {x["n_cross"]}' + (f' · 주요 외신 {len(x["major"])}곳' if x["major"] else "")
        with st.expander(f'{x["name"]} — {badge}', expanded=x["n_cross"] > 0):
            st.markdown(f'<div class="mc-sum">{html.escape(x["comment"])}<br><span class="m" style="font-size:.8rem;color:#6B7A85">'
                        f'지표: {" · ".join(f"{a} {b}" for a, b in x["drivers"])}</span></div>', unsafe_allow_html=True)
            rows = []
            for l in x["links"]:
                ok = "—" if l["ok"] is None else ('<span style="color:#1D7A4C">✔ 가설대로</span>' if l["ok"]
                                                  else '<span style="color:#B7791F">✘ 반대로</span>')
                rows.append([f'{html.escape(l["name"])} <span style="color:#6B7A85">{html.escape(l["sym"])}</span>',
                             "같이 움직임" if l["how"] == "same" else "반대로 움직임", l["move"], ok, "§" + html.escape(l["why"])])
            st.markdown(_table(["관련 섹터·지표", "가설", "5일 실제", "결과", "이유(가설)"], rows), unsafe_allow_html=True)
            for nw in x["news"][:6]:
                maj = f' · <b>주요 외신</b> {html.escape(", ".join(nw["major"]))}' if nw.get("major") else ""
                st.markdown(f'<div class="mc-news">{_chip(nw["status"])} '
                            f'<a href="{html.escape(nw["url"])}" target="_blank">{html.escape(nw["title"])}</a>'
                            f'<div class="m">{html.escape(", ".join(nw["sources"]))}{maj}</div></div>', unsafe_allow_html=True)


# ═══════════════════════════ 경제지표 ═══════════════════════════
@st.cache_data(ttl=6 * 3600, show_spinner="경제지표를 받는 중이에요…")
def _econ_series() -> dict:
    return econ.fetch_series()


def _val(v, e) -> str:
    if v is None:
        return "—"
    if e["unit"] == "천명":
        return f"{v:+,.0f}천명"
    if e["unit"] == "건":
        return f"{v:,.0f}"
    return f"{v:,.2f}{e['unit']}"


def tab_econ(snap: dict) -> None:
    series = _econ_series()
    summ = econ.summary(series)
    rows = []
    for e in C.ECON:
        s = summ.get(e["id"])
        rows.append([e["name"], _val(s and s["last"], e), _val(s and s["prev"], e),
                     f'{s["date"]:%Y-%m-%d}' if s else "—",
                     f'{_val(s and s["y_lo"], e)} ~ {_val(s and s["y_hi"], e)}' if s else "—", "§" + html.escape(e["read"])])
    st.markdown("#### 미국 경제지표 한눈에")
    st.markdown(_table(["지표", "최근", "직전", "기준일", "1년 범위", "읽는 법"], rows), unsafe_allow_html=True)
    st.caption("FRED(세인트루이스 연준) 자료. CPI·PCE·산업생산은 전년 대비 %, 고용은 전월 대비 증감, 소매판매는 전월 대비 %예요.")

    st.markdown("#### 지표 자세히 보기 + 발표일 각국 지수 반응")
    names = {e["name"]: e for e in C.ECON}
    pick = st.radio("지표", list(names), horizontal=True, key="ec_pick")
    e = names[pick]
    s = series.get(e["id"])
    if s is None or s.empty:
        st.info("이 지표를 받지 못했어요.")
        return
    span = st.radio("기간", ["1년", "5년", "전체(약 12년)"], horizontal=True, key="ec_span")
    cut = {"1년": 1, "5년": 5}.get(span)
    show = s[s["date"] >= s["date"].iloc[-1] - pd.DateOffset(years=cut)] if cut else s
    st.plotly_chart(charts.line(show, f'{e["name"]} ({e["unit"] or "지수"})', zero=e["how"] in ("diff", "mom")),
                    key="ec_chart", config={"displaylogo": False})
    sahm = econ.sahm(series.get("UNRATE")) if e["id"] == "UNRATE" else None
    if sahm is not None:
        st.markdown(f'<div class="mc-sum">삼의 법칙 값 <b>{sahm:.2f}%p</b> — '
                    + ("0.5 이상: 과거엔 경기 침체 신호였어요" if sahm >= 0.5 else "0.5 아래: 침체 신호는 아직이에요") + "</div>",
                    unsafe_allow_html=True)
    rel = econ.releases(e, s, snap.get("px", {}))
    if not rel["rows"]:
        st.caption("이 지표는 발표일 반응 분석을 하지 않아요(CPI·근원 CPI·근원 PCE·비농업 고용·실업률만).")
        return
    stats = econ.reaction_stats(rel["rows"])
    st.caption(("발표일은 FRED 발표 일정 기준이에요." if rel["exact"] else
                "발표일은 규칙으로 추정했어요(고용 = 다음 달 첫 금요일, CPI = 다음 달 둘째 주 수요일 무렵, PCE = 다음 달 마지막 금요일). "
                "정확한 날짜를 쓰려면 Secrets에 무료 FRED_API_KEY를 넣어 주세요.")
               + " 미국·유럽은 발표 당일, 한국·일본·대만은 다음 거래일(한국시간 밤 발표라서) 등락이에요. "
               "'뜨거움/식음'은 시장 예상치가 아니라 직전 값(고용은 직전 3개월 평균) 대비예요.")
    head = ["기준월", "발표일", "값", "비교 기준", "판정"] + [n for _, n, _ in C.REACT]
    body = []
    for r in rel["rows"]:
        hot = '<span style="color:%s">%s</span>' % ((UP, "뜨거움") if r["hot"] else (DOWN, "식음"))
        cells = [_pp(r["react"][sym]) if sym == "^TNX" else _p(r["react"][sym]) for sym, _, _ in C.REACT]
        body.append([f'{r["ref"]:%Y-%m}', f'{r["day"]:%m/%d}', _val(r["value"], e), _val(r["base"], e), hot] + cells)
    st.markdown(_table(head, body, left=2), unsafe_allow_html=True)
    st.markdown("**뜨거울 때 vs 식을 때 평균 반응**")
    st.markdown(_table(["지수·지표", "뜨거울 때", "식을 때", "표본"],
                       [[x["name"] + (" (다음 거래일)" if x["asia"] else ""),
                         _pp(x["hot"]) if x["sym"] == "^TNX" else _p(x["hot"]),
                         _pp(x["cool"]) if x["sym"] == "^TNX" else _p(x["cool"]),
                         f'{x["n_hot"]} / {x["n_cool"]}'] for x in stats]), unsafe_allow_html=True)
    st.caption("표본이 12번 안팎이라 평균은 참고용이에요. 같은 날 다른 뉴스(실적·전쟁 등)도 섞여 있어요.")
    st.markdown(f"#### 🤖 {e['name']} 해석 (기사·리포트 검색)")
    _ai_block(f"econ_{e['id']}", ai.indicator_context(e, summ.get(e["id"]), rel, stats, sahm), ai.INDICATOR_ASK,
              f"{e['name']} AI 해석 만들기")
