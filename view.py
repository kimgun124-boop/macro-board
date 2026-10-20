"""화면 그리기. 데이터는 macro.py, 이 파일은 그리기만. 탭마다 함수 하나예요."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import ai
import alloc
import analog
import charts
import corr
import digest
import flows
import report
import config as C
import econ
import events
import issues
import portfolio
import macro
import sources as S
import trend

UP, DOWN, FLAT = "#D6333B", "#1F66C9", "#51616C"     # 한국식: 상승 빨강, 하락 파랑
CHIP = {"교차확인": "#1D7A4C", "단일출처": "#51616C", "상충": "#B7791F", "주장": "#C53030", "의견": "#7B5EA7", "없음": "#9AA5AE"}

# 밸류체인 신고가 보드(very)의 기본 스타일을 그대로 가져왔어요. 색·카드·탭 모양은 theme.py(very와 같은 파일)가 덮어써요.
CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stMarkdown {
  font-family: 'Pretendard Variable', Pretendard, 'Malgun Gothic', sans-serif;
}
.stApp h1 { font-weight: 800; letter-spacing: -0.025em; }
.status { color: #51616C; font-size: 0.88rem; margin: -0.4rem 0 0.9rem; }
/* 메인 탭 3묶음(very와 같은 방식): 시황 해석 · 시장 데이터 · 경제지표 */
.st-key-main_tabs [role="tablist"] { gap: 0.3rem; border-bottom: 2px solid #DCE3E7; padding-bottom: 0; }
.st-key-main_tabs [role="tab"] {
  position: relative; --gc: #51616C; --gt: #F1F4F6;
  background: var(--gt); border: 1px solid #E3E8EB; border-top: 3px solid var(--gc); border-bottom: none;
  border-radius: 8px 8px 0 0; padding: 1.15rem 0.85rem 0.45rem !important; overflow: visible !important; }
.st-key-main_tabs [role="tab"]:nth-child(6),
.st-key-main_tabs [role="tab"]:nth-child(9) { margin-left: 0.9rem; }
.st-key-main_tabs [role="tab"]::before {
  position: absolute; top: 0.2rem; left: 0.85rem; font-size: 0.64rem; font-weight: 800;
  letter-spacing: 0.02em; color: var(--gc); white-space: nowrap; content: ""; z-index: 2; }
.st-key-main_tabs [role="tab"]:nth-child(1)::before { content: "판단·해석"; }
.st-key-main_tabs [role="tab"]:nth-child(6)::before { content: "시장 데이터"; }
.st-key-main_tabs [role="tab"]:nth-child(9)::before { content: "수급·지표"; }
.st-key-main_tabs [role="tab"] p { color: #3A4852; font-size: 0.98rem !important; }
.st-key-main_tabs .react-aria-SelectionIndicator, .st-key-main_tabs [data-baseweb="tab-highlight"], .st-key-main_tabs [data-baseweb="tab-border"] { display: none; }
.st-key-main_tabs [role="tabpanel"] [role="tab"]::before { content: none !important; }
.sec-h { display: flex; align-items: baseline; justify-content: space-between; gap: 0.6rem; margin: 1rem 0 0.5rem; }
.sec-h b { font-size: 1.12rem; font-weight: 800; color: #16212B; }
.sec-h span { font-size: 0.78rem; color: #7A8A94; }
.verdict { border-left: 6px solid var(--vc); background: #FFFFFF; border-radius: 12px; padding: 0.8rem 1rem;
  box-shadow: 0 1px 2px rgba(0,0,0,.04); margin-bottom: 0.7rem; }
.v-top { display: flex; justify-content: space-between; gap: 0.5rem; font-size: 0.76rem; color: #7A8A94; }
.v-lab { font-weight: 700; letter-spacing: .02em; }
.v-title { font-size: 1.55rem; font-weight: 900; color: var(--vc); line-height: 1.25; margin-top: 0.1rem; }
.v-act { font-size: 0.95rem; font-weight: 600; color: #26343E; margin-top: 0.15rem; }
.idx-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(135px, 1fr)); gap: 0.6rem; margin: 0 0 0.9rem; }
.idx { background: #FFFFFF; border: 1px solid #DCE3E7; border-radius: 12px; padding: 0.7rem 0.9rem; }
.idx-name { font-size: 0.85rem; color: #51616C; }
.idx-name small { margin-left: 0.3rem; color: #8A979F; }
.idx-val { font-size: 1.15rem; font-weight: 800; color: #16212B; font-variant-numeric: tabular-nums; }
.idx-chg { display: block; font-size: 0.85rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.idx svg { display: block; width: 100%; height: 28px; margin-top: 0.3rem; }
.idx-badge { display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 0.1rem 0.45rem;
  border-radius: 6px; margin-top: 0.25rem; }
.idx-badge.on { background: var(--pri-soft); color: var(--pri-ink); }
.idx-badge.off { background: #F4E1E2; color: #A2343B; }
.idx-badge.neutral { background: #F3F4F8; color: var(--sub); }
/* 이 보드만의 카드·표 (theme 색 토큰 사용) */
.mc-sum{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:0.95rem 1.15rem;margin:4px 0 14px;line-height:1.75}
.mc-sum b{font-weight:700}
.mc-wrap{overflow-x:auto;margin-bottom:10px;background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
.mc-t{width:100%;border-collapse:collapse;font-size:.88rem;font-variant-numeric:tabular-nums}
.mc-t th{background:#F7F7FB;color:var(--sub);font-weight:600;text-align:right;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
.mc-t td{text-align:right;padding:7px 10px;border-bottom:1px solid var(--line2);white-space:nowrap}
.mc-t tbody tr:hover td{background:#FAF9FF}
.mc-t .l{text-align:left}
.mc-t .note{color:var(--sub);font-size:.78rem;white-space:normal;min-width:12rem;text-align:left}
.mc-chip{display:inline-block;padding:0 8px;border-radius:999px;border:1px solid;font-size:.75rem;line-height:1.6;background:#fff}
.mc-legend{font-size:.8rem;color:var(--sub);margin:-4px 0 10px}
.mc-news{border:1px solid var(--line);border-radius:14px;padding:10px 14px;margin-bottom:8px;background:var(--card);box-shadow:var(--shadow)}
.mc-news:hover{border-color:#CFC8FF;background:#FAF9FF}
.mc-news .h{font-weight:700;margin:4px 0}
.mc-news .m{font-size:.78rem;color:var(--sub)}
.mc-news a{color:inherit;text-decoration:none}
.mc-bar{display:grid;grid-template-columns:minmax(7rem,max-content) 1fr 4.5rem;gap:6px 10px;align-items:center;font-size:.86rem;background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow);padding:12px 14px}
.mc-bar .track{position:relative;height:14px}
.mc-bar .mid{position:absolute;left:50%;top:0;bottom:0;border-left:1px solid #D9DCE8}
.mc-bar .fill{position:absolute;top:2px;bottom:2px;border-radius:4px}
.mc-bar .v{text-align:right;font-variant-numeric:tabular-nums}
.mc-card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:10px 12px 4px;margin-bottom:10px}
.mc-card .t{display:flex;justify-content:space-between;align-items:baseline;gap:6px}
.mc-card .s{font-size:.78rem;margin:2px 0 0}
.mc-card .c{font-size:.78rem;color:var(--sub);margin:2px 0 6px}
.rep{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow-lg);padding:1.2rem 1.4rem;margin-bottom:1rem}
.rep-top{display:flex;justify-content:space-between;align-items:center;gap:.5rem;flex-wrap:wrap}
.rep-t{font-size:1.35rem;font-weight:900;color:var(--ink);letter-spacing:-.03em;margin:.2rem 0}
.rep-lead{font-size:1rem;font-weight:600;color:#26343E;background:var(--pri-soft);border-radius:12px;padding:.6rem .85rem;margin:.5rem 0 0}
.st-key-rep_body h2{font-size:1.08rem !important;font-weight:800;margin:1rem 0 .35rem;padding:0;border-left:4px solid var(--pri);padding-left:.5rem}
.st-key-rep_body table{width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}
.st-key-rep_body th{background:#F7F7FB;color:var(--sub);font-weight:600}
.st-key-rep_body li, .st-key-rep_body p{font-size:.92rem;line-height:1.65}
.dg .dg-h, .dg-h{font-weight:800;font-size:.98rem;margin:0 0 6px;display:flex;justify-content:space-between;gap:8px}
.dg-h span{font-weight:400;font-size:.76rem;color:var(--sub)}
.dg-row{display:flex;gap:10px;padding:7px 0;border-top:1px solid var(--line2)}
.dg-row:first-of-type{border-top:none}
.dg-row a{color:var(--ink);font-weight:700;text-decoration:none}
.dg-no{color:var(--pri);font-size:1.05rem;min-width:1.1rem}
.dg-tp{display:inline-block;font-size:.72rem;font-weight:700;color:var(--pri-ink);background:var(--pri-soft);border-radius:6px;padding:0 6px;margin-right:6px}
.dg-m{font-size:.76rem;color:var(--sub)}
.dg-ko{margin-top:3px}
.dg-ko span{display:inline-block;font-size:.72rem;color:#374151;background:#F3F4F8;border-radius:6px;padding:0 6px;margin:0 4px 2px 0}
.dg-card .dg-t{font-size:.86rem;font-weight:700;line-height:1.4;margin:4px 0 2px}
.dg-card .dg-t a{color:var(--ink);text-decoration:none}
.dg-mv{font-size:.76rem;color:#374151;margin-top:4px;font-variant-numeric:tabular-nums}
.dg-path{font-size:.74rem;color:var(--sub);margin-top:3px}
.st-key-rep_news h2{font-size:1rem !important}
.st-key-rep_news table{width:100%;font-size:.86rem}
.ev .ev-d{color:var(--pri);margin-right:4px}
.ev .ev-est{font-size:.68rem;color:#B7791F;border:1px solid #E9C46A;border-radius:6px;padding:0 4px}
.ev .ev-n{font-weight:800;font-size:.98rem;margin:3px 0}
.ev .ev-w{font-size:.76rem;color:var(--sub);line-height:1.45}
.ev .ev-p{font-size:.76rem;color:#374151;margin-top:4px;font-variant-numeric:tabular-nums}
.cr{margin:-4px 0 6px}
.cr .cr-v{font-size:.98rem;font-weight:800;letter-spacing:-.01em;margin-bottom:3px}
.cr ul{list-style:none;padding:0;margin:0}
.cr li{font-size:.88rem;line-height:1.55;color:#26343E;font-variant-numeric:tabular-nums}
.cr.big .cr-v{font-size:1.15rem}
.cr.big li{font-size:.98rem}
.al-cap{margin-top:.45rem;font-size:.84rem;font-weight:700;color:#A2343B;background:#FBE9EA;border-radius:8px;padding:.35rem .6rem}
.al-split-t{font-size:.86rem;font-weight:800;color:var(--ink);margin:2px 0 6px}
.al-split{display:flex;height:34px;border-radius:10px;overflow:hidden;font-size:.86rem;font-weight:800;color:#fff}
.al-split div{display:flex;align-items:center;justify-content:center;white-space:nowrap;min-width:3.5rem}
.al-lines div{margin:2px 0}
.al-k{display:inline-block;font-size:.74rem;font-weight:800;border-radius:6px;padding:.05rem .45rem;margin-right:.45rem}
.al-pts{display:flex;align-items:center;gap:6px;justify-content:flex-end}
.al-pts span{color:#8A979F;font-size:.75rem}
.al-track{width:70px;height:8px;background:#EEF0F6;border-radius:99px;overflow:hidden}
.al-track div{height:100%;border-radius:99px}
.stApp [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stPlotlyChart"] { border: none; box-shadow: none; padding: 0; }
@media (max-width: 640px) {
  .idx-row { gap: 0.35rem; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .idx { padding: 0.5rem 0.55rem; }
  .idx-name { font-size: 0.74rem; }
  .idx-val { font-size: 0.98rem; }
  .st-key-main_tabs [role="tab"]:nth-child(6), .st-key-main_tabs [role="tab"]:nth-child(9) { margin-left: 0; }
}
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
    notes = {i for i, c in enumerate(rows[0]) if str(c).startswith("§")} if rows else set()
    th = "".join(f'<th class="{"l" if i < left or i in notes else ""}">{h}</th>' for i, h in enumerate(head))
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


def _sec(title: str, sub: str = "") -> None:
    """very와 같은 제목줄(보라 막대 + 굵은 제목 + 오른쪽 작은 설명)."""
    st.markdown(f'<div class="sec-h"><b>{html.escape(title)}</b><span>{html.escape(sub)}</span></div>',
                unsafe_allow_html=True)


def _spark(vals: list[float] | None, color: str) -> str:
    if not vals or len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i / (len(vals) - 1) * 100:.1f},{28 - (v - lo) / rng * 26 - 1:.1f}" for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 100 28" preserveAspectRatio="none"><polyline points="{pts}" fill="none" '
            f'stroke="{color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>')


# 맨 위 핵심 숫자 카드(very의 지수 카드 모양)
KPI = [("^GSPC", "S&P 500", "idx"), ("^IXIC", "나스닥", "idx"), ("^KS11", "코스피", "idx"), ("^KQ11", "코스닥", "idx"),
       ("fred:DGS10", "미 10년물", "rate"), ("KRW=X", "원/달러", "idx"), ("CL=F", "WTI 유가", "idx"), ("^VIX", "VIX", "idx")]


def _kpi(snap: dict, key: str, name: str, kind: str) -> str:
    sm, tr = snap["sm"], snap.get("trend", {})
    s = (snap["fred"].get("DGS10") or sm.get("^TNX")) if key == "fred:DGS10" else sm.get(key)
    if not s:
        return f'<div class="idx"><div class="idx-name">{name}</div><div class="idx-val">—</div></div>'
    if kind == "rate":
        v = s.get("a1")
        chg = "" if v is None else f'<span class="idx-chg" style="color:{_c(v)}">{v:+.3f}%p</span>'
        val = f'{s["last"]:.3f}%'
        col = _c(v)
    else:
        v = s.get("d1")
        chg = "" if v is None else f'<span class="idx-chg" style="color:{_c(v)}">{v:+.2f}%</span>'
        val = f'{s["last"]:,.2f}' if s["last"] < 10000 else f'{s["last"]:,.0f}'
        col = _c(s.get("d20"))
    t = tr.get(key)
    badge = ""
    if t:
        cls = "on" if t["stage"] in ("상승 추세", "추세 속 눌림") else ("off" if t["stage"] == "하락 추세" else "neutral")
        badge = f'<span class="idx-badge {cls}">{t["stage"]}</span>'
    return (f'<div class="idx"><div class="idx-name">{name}<small>{s["date"]:%m/%d}</small></div>'
            f'<div class="idx-val">{val}</div>{chg}{badge}{_spark(s.get("spark"), col)}</div>')


def header(snap: dict) -> None:
    st.markdown('<div class="idx-row">' + "".join(_kpi(snap, *k) for k in KPI) + "</div>", unsafe_allow_html=True)
    lines = macro.facts(snap)
    st.markdown('<div class="mc-legend">' + " · ".join(html.escape(x) for x in lines) + "<br>검증: "
                + " ".join(_chip(k) for k in ("교차확인", "단일출처", "상충")) +
                f" 야후 종가를 stooq·네이버·FRED와 같은 날짜끼리 맞춰 봐요(차이 {C.TOL}% 안이면 교차확인). 시세는 15분 안팎 지연이에요.</div>",
                unsafe_allow_html=True)


def _seg(label: str, options: list, key: str, where=None, default=None):
    """very처럼 알약 버튼 묶음(segmented control). 항상 하나는 선택돼 있어요."""
    w = where or st
    return w.segmented_control(label, options, default=default if default is not None else options[0],
                               required=True, key=key) or (default if default is not None else options[0])


def period_pick() -> tuple[str, str]:
    period = _seg("기간", ["1일", "5일", "20일"], key="mc_period")
    return period, {"1일": "d1", "5일": "d5", "20일": "d20"}[period]


def tab_markets(snap: dict) -> None:
    sm, ver, fred = snap["sm"], snap["ver"], snap["fred"]
    _sec("세계 주요 지수")
    rows = []
    for i in C.INDICES:
        s = sm.get(i["yf"])
        v, note = ver.get(i["yf"], ("없음", ""))
        rows.append([i["region"], i["name"], f'{s["last"]:,.2f}' if s else "—", _p(s and s["d1"]), _p(s and s["d5"]),
                     _p(s and s["d20"]), _ma(s), f'{s["date"]:%m/%d}' if s else "—", _chip(v), "§" + html.escape(note)])
    st.markdown(_table(["지역", "지수", "종가", "1일", "5일", "20일", "50일선", "기준일", "검증", "대조"], rows, left=2),
                unsafe_allow_html=True)

    _sec("금리 · 환율 · 원자재")
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

    _sec("시장 체력 · 위험 지표")
    rows = []
    for x in C.VOL:
        s = sm.get(x["yf"])
        rows.append(["변동성", x["name"], f'{s["last"]:.2f}' if s else "—", _p(s and s["d1"]), _p(s and s["d20"]),
                     f'{s["date"]:%m/%d}' if s else "—", "§" + x["read"]])
    for f in C.FRED:
        s = fred.get(f["id"])
        rows.append([f["group"], f["name"], f'{s["last"]:.2f}%' if s else "—", _pp(s and s["a1"]), _pp(s and s.get("a20")),
                     f'{s["date"]:%m/%d}' if s else "—",
                     "§" + f["read"] + (" (FRED)" if s else " · 못 받음: FRED 접속이 막혀요. Secrets에 FRED_API_KEY를 넣으면 받아요")])
    # FRED가 막히면 ETF로 신용 위험을 대신 봐요(하이일드·투자등급 회사채 ETF vs 국채 ETF)
    ief = sm.get("IEF")
    for sym, name, fid in (("HYG", "하이일드", "BAMLH0A0HYM2"), ("LQD", "투자등급(BBB 근처)", "BAMLC0A4CBBB")):
        e = sm.get(sym)
        if fred.get(fid) or not e or not ief or e["d20"] is None or ief["d20"] is None:
            continue
        rel1 = None if e["d1"] is None or ief["d1"] is None else e["d1"] - ief["d1"]
        rows.append(["신용(대체)", f"{name} ETF − 국채 ETF ({sym}−IEF)", f'{e["d20"] - ief["d20"]:+.2f}%p (20일)', _pp(rel1),
                     _p(e["d20"]), f'{e["date"]:%m/%d}',
                     "§FRED 스프레드를 못 받아서 ETF로 대신 봐요. 음수가 커지면 회사채가 국채보다 약함 = 신용 위험이 커지는 중"])
    rsp, spy = sm.get("RSP"), sm.get("SPY")
    if rsp and spy and rsp["d20"] is not None and spy["d20"] is not None:
        rows.append(["시장 폭", "동일가중 − 시총가중 (20일)", f'{rsp["d20"] - spy["d20"]:+.2f}%p', _p(rsp["d1"]), _p(rsp["d20"]),
                     f'{rsp["date"]:%m/%d}', "§음수면 소수 대형주가 지수를 끌고 가는 중. 1일·20일은 RSP 등락"])
    st.markdown(_table(["구분", "지표", "값", "1일", "20일", "기준일", "읽는 법"], rows, left=2), unsafe_allow_html=True)


def tab_sectors(snap: dict) -> None:
    sm, ver = snap["sm"], snap["ver"]
    period, k = period_pick()
    _sec("미국 섹터 ETF")
    sec = dict(C.SECTORS)
    st.markdown(_bars([(f"{n} {s}", (sm.get(s) or {}).get(k)) for s, n in C.SECTORS]), unsafe_allow_html=True)

    _sec("섹터별 대장주")
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
        _sec("테마 ETF")
        st.markdown(_bars([(f"{n} {s}", (sm.get(s) or {}).get(k)) for s, n in C.THEMES]), unsafe_allow_html=True)
    with c2:
        _sec("한국 대장주")
        st.markdown(_bars([(n, (sm.get(c) or {}).get(k)) for c, n, _ in C.KR_LEADERS]), unsafe_allow_html=True)
        st.caption("네이버 일봉(장중 갱신). 단일출처예요.")


def tab_news(snap: dict) -> None:
    news = snap.get("news") or []
    _sec("지금 뉴스 요약", "새 뉴스가 들어오면 15분마다 다시 정리 · 영어 제목엔 한국어 핵심어")
    _claude_news()
    _digest_block(digest.build(snap), cards=9, items=0)
    _sec("전체 뉴스", "사실 라벨로 거르기")
    pick = _seg("보기", ["사실만(교차확인·단일출처)", "교차확인만", "주장·의견까지 전부"], key="mc_news")
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


# ═══════════════════════════ 비중 판단(첫 탭) + AI ═══════════════════════════


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


@st.cache_data(ttl=15 * 60, show_spinner=False)
def _alloc_hist(at: str, _snap: dict) -> pd.DataFrame:
    """과거 점수(15분 캐시). at = 스냅샷 시각(캐시 키)."""
    try:
        ten = S.fred("DGS10", days=1000)
    except Exception:  # noqa: BLE001
        ten = None
    return alloc.history(_snap, ten)


def _pts_bar(s: dict) -> str:
    if s["pts"] is None:
        return '<span style="color:#9AA5AE">—</span>'
    r = s["pts"] / s["max"]
    col = UP if r >= 0.7 else "#B7791F" if r >= 0.4 else DOWN
    return (f'<div class="al-pts"><div class="al-track"><div style="width:{r * 100:.0f}%;background:{col}"></div></div>'
            f'<b style="color:{col}">{s["pts"]:g}</b><span>/{s["max"]}</span></div>')


def _tilt_table(rows: list[dict]) -> str:
    if not rows:
        return '<div class="mc-legend">해당 없음</div>'
    body = [[f'{html.escape(r["name"])} <span style="color:#8A979F;font-size:.75rem">{r["where"]}</span>',
             f'<span class="mc-chip" style="color:{trend.STAGE_COLOR.get(r["stage"].split("(")[0], FLAT)};'
             f'border-color:{trend.STAGE_COLOR.get(r["stage"].split("(")[0], FLAT)}">{html.escape(r["stage"])}</span>',
             _p(r["rel"], 1), _p(r["from_high"], 1)] for r in rows]
    return _table(["섹터·종목", "추세", "20일 상대", "고점 대비"], body)


def _sgn(v) -> str:
    return "—" if v is None else f'<b style="color:{_c(v)}">{v:+.0f}</b>'


def _events_block(snap: dict, days: int = 21) -> None:
    today = pd.Timestamp(snap["at"].strftime("%Y-%m-%d"))
    ev = events.calendar(today, days)
    _sec("📅 다가오는 이벤트", f"{days}일 안 · 추정은 발표 규칙으로 계산한 날짜")
    if not ev:
        st.caption("가까운 큰 이벤트가 없어요.")
        return
    fr = events.fomc_reaction(snap.get("px", {}), today)
    ex = events.expiry_reaction(snap.get("px", {}), today)
    cards = []
    for e in ev:
        past = ""
        if e["kind"] == "fomc" and fr:
            n, k = fr["nasdaq"], fr["kospi"]
            past = (f'지난 {n["n"]}번: 나스닥 평균 {n["avg"]:+.1f}% (평균 흔들림 ±{n["abs"]:.1f}%)' if n else "") + \
                   (f' · 다음 날 코스피 평균 {k["avg"]:+.1f}% (±{k["abs"]:.1f}%)' if k else "")
        elif e["kind"] in ("kr_opt", "kr_quad") and ex:
            past = f'지난 {ex["n"]}번 만기일 코스피 평균 흔들림 ±{ex["abs"]:.2f}% (보통 날 ±{ex["normal"]:.2f}%)'
        dd = "오늘" if e["dday"] == 0 else f'D-{e["dday"]}'
        cards.append(f'<div class="idx ev"><div class="idx-name"><b class="ev-d">{dd}</b> {html.escape(e["time"])}'
                     + (' <span class="ev-est">추정</span>' if e["est"] else "") + f'</div><div class="ev-n">{html.escape(e["name"])}</div>'
                     f'<div class="ev-w">{html.escape(e["why"])}</div>' + (f'<div class="ev-p">{past}</div>' if past else "") + "</div>")
    st.markdown('<div class="idx-row" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))">' + "".join(cards) + "</div>",
                unsafe_allow_html=True)
    if any(e["kind"] == "fomc" and e["dday"] <= 7 for e in ev):
        st.markdown('<div class="mc-legend">FOMC가 7일 안이에요. 블로그 관점: 이벤트 앞에선 시나리오를 두 갈래로 세우고, 비중을 크게 늘리는 건 결과를 본 뒤로.</div>',
                    unsafe_allow_html=True)


def _analog_block() -> None:
    _sec("📉 과거 비슷한 구간", "지금과 고점 대비 낙폭(±3%p)·50·200일선 위치가 같았던 날 · 최근 10년")
    lp = _long()
    res = analog.all_for(lp)
    rows = []
    for name, r in res.items():
        if not r:
            continue
        now = r["now"]
        pos = f'50일선 {"위" if now["a50"] else "아래"} · 200일선 {"위" if now["a200"] else "아래"}'
        if not r["n"]:
            rows.append([f"<b>{name}</b>", _p(now["dd"], 1), pos, "0번", "—", "—", "—", "—"])
            continue
        rows.append([f"<b>{name}</b>", _p(now["dd"], 1), pos, f'{r["n"]}번',
                     f'{_p(r["f20"], 1)} <span style="color:#8A979F;font-size:.75rem">오른 경우 {r["f20_up"]:.0f}%</span>',
                     "—" if r["f60"] is None else f'{_p(r["f60"], 1)} <span style="color:#8A979F;font-size:.75rem">오른 경우 {r["f60_up"]:.0f}%</span>',
                     f'{_p(r["worst20"], 1)} ~ {_p(r["best20"], 1)}',
                     f'{_p(r["base20"], 1)} <span style="color:#8A979F;font-size:.75rem">오른 경우 {r["base20_up"]:.0f}%</span>'])
    if not rows:
        st.caption("10년치 지수를 받지 못했어요.")
        return
    st.markdown(_table(["지수", "지금 고점 대비", "지금 위치", "비슷한 날", "그 뒤 20일 평균", "그 뒤 60일 평균", "20일 최악~최고", "모든 날 20일 평균"],
                       rows), unsafe_allow_html=True)
    with st.expander("비슷했던 날 목록"):
        for name, r in res.items():
            if r and r["n"]:
                body = [[f'{x["date"]:%Y-%m-%d}', _p(x["dd"], 1), _p(x["r20"], 1), _p(x["f20"], 1), _p(x["f60"], 1)]
                        for _, x in r["rows"].head(12).iterrows()]
                st.markdown(f"**{name}**")
                st.markdown(_table(["날짜", "고점 대비", "직전 20일", "그 뒤 20일", "그 뒤 60일"], body), unsafe_allow_html=True)
    st.caption("같은 사건이 여러 번 세어지지 않게 20거래일 이상 떨어진 날만 셌어요. 과거 통계이지 예측이 아니에요.")


def tab_alloc(snap: dict) -> None:
    _, fl = _flows()
    a = alloc.build(snap, fl)
    b, sp = a["band"], a["split"]
    got, tot = a["coverage"]
    h = _alloc_hist(f'{snap["at"]:%Y%m%d%H%M}', snap)
    ch = alloc.changes(h)

    c1, c2, c3 = st.columns([1.25, 1, 1], vertical_alignment="center")
    with c1:
        cap = "".join(f'<div class="al-cap">⛔ {html.escape(t)}</div>' for _, t in a["caps"])
        st.markdown(
            f'<div class="verdict" style="--vc:{b["color"]}"><div class="v-top"><span class="v-lab">계좌 비중 판단</span>'
            f'<span>신호 {got}/{tot}개 · {snap["at"]:%m/%d %H:%M}</span></div>'
            f'<div class="v-title">{b["name"]} · 주식 {b["equity"]}</div>'
            f'<div class="v-act">{html.escape(b["say"])}</div>{cap}</div>', unsafe_allow_html=True)
    with c2:
        st.plotly_chart(charts.gauge(a["score"], alloc.BANDS), key="al_gauge", config={"displayModeBar": False})
        if a["caps"] and a["raw"] > a["score"] + 0.5:
            st.markdown(f'<div class="mc-legend" style="text-align:center">신호만 더하면 {a["raw"]:.0f}점 → 레드라인 상한 {a["score"]:.0f}점</div>',
                        unsafe_allow_html=True)
        if ch:
            st.markdown(f'<div class="mc-legend" style="text-align:center">가격 신호 점수 1일 {_sgn(ch["d1"])} · 5일 {_sgn(ch["d5"])}'
                        + (f' · 5일 전 {ch["band_then"]} → 지금 {ch["band_now"]}' if ch["band_then"] != ch["band_now"] else "")
                        + "</div>", unsafe_allow_html=True)
    with c3:
        rel = sp.get("rel20")
        st.markdown(
            f'<div class="al-split-t">주식 안에서 나누기</div><div class="al-split">'
            f'<div style="width:{sp["kr"]}%;background:{UP}">한국 {sp["kr"]}%</div>'
            f'<div style="width:{sp["us"]}%;background:#111827">미국 {sp["us"]}%</div></div>'
            f'<div class="mc-legend" style="margin:4px 0 8px">한국 신호 {0 if sp["kr_rate"] is None else sp["kr_rate"] * 100:.0f}점 · '
            f'미국 신호 {0 if sp["us_rate"] is None else sp["us_rate"] * 100:.0f}점'
            + (f' · 20일 코스피−나스닥 {rel:+.1f}%p' if rel is not None else "") + "</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.group_bars(a["groups"], height=170), key="al_groups", config={"displayModeBar": False})

    # 한 줄씩: 끌어내린 것 · 받쳐 준 것 · 오늘 해석
    drag = " · ".join(f'{html.escape(s["name"])} {html.escape(s["value"])} ({s["pts"]:g}/{s["max"]})' for s in a["drag"]) or "없음"
    sup = " · ".join(f'{html.escape(s["name"])} {html.escape(s["value"])} ({s["pts"]:g}/{s["max"]})' for s in a["support"]) or "없음"
    reps = report.all_reports()
    lead = f'<div><span class="al-k" style="background:#EFEDFF;color:#4532D9">오늘 해석</span>{html.escape(reps[0]["lead"])} ' \
           f'<span style="color:#8A979F;font-size:.78rem">({reps[0]["when"]}, 🌐 탭)</span></div>' if reps and reps[0]["lead"] else ""
    moved = ""
    if ch and ch["moved"]:
        moved = ('<div><span class="al-k" style="background:#F3F4F8;color:#374151">5일 변화</span>' + " · ".join(
            f'{html.escape(m["name"])} {m["from"]:g}→<b style="color:{UP if m["to"] > m["from"] else DOWN}">{m["to"]:g}</b>'
            + (f'/{m["max"]}' if m["max"] else "") for m in ch["moved"][:5]) + "</div>")
    st.markdown(f'<div class="mc-sum al-lines"><div><span class="al-k" style="background:#E8EEF8;color:{DOWN}">끌어내림</span>{drag}</div>'
                f'<div><span class="al-k" style="background:#FBE9EA;color:{UP}">받쳐 줌</span>{sup}</div>{moved}{lead}</div>',
                unsafe_allow_html=True)

    _sec("비중이 바뀌는 조건", "점수가 가장 많이 오르는 순서")
    if a["triggers"]:
        st.markdown('<div class="idx-row" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))">' + "".join(
            f'<div class="idx"><div class="idx-name">{html.escape(nm)}</div><div class="idx-val" style="font-size:1rem">'
            f'{html.escape(t)}</div><span class="idx-badge on">+{g}점</span></div>' for t, g, nm in a["triggers"]) + "</div>",
            unsafe_allow_html=True)
    else:
        st.caption("모든 신호가 만점 근처예요.")

    _events_block(snap, days=21)

    _sec("신호 12개", "점수 = 보내 주신 블로그 기준을 숫자로 옮긴 것")
    rows = [[f'<span style="color:#8A979F">{s["group"]}</span>', f'<b>{html.escape(s["name"])}</b>', html.escape(s["value"]),
             _pts_bar(s), "§" + html.escape(s["why"]), "§" + html.escape(s["next"] or "—")] for s in a["signals"]]
    st.markdown(_table(["묶음", "신호", "지금", "점수", "근거", "좋아지려면"], rows, left=3), unsafe_allow_html=True)
    st.markdown('<div class="mc-legend">구간: ' + " · ".join(
        f'<b style="color:{c}">{n}</b> {lo}점+ 주식 {e}' for lo, n, e, c, _ in alloc.BANDS) +
        ' · 레드라인: 10년물 5% 이상이면 축소 위로 못 감, 나스닥 -3%·전닉 동반 하락이면 중립 위로 못 감</div>',
        unsafe_allow_html=True)

    _sec("어디에 싣나", "이평선 추세 + 20일 상대 강도(미국은 S&P, 한국은 코스피 대비)")
    t1, t2 = st.columns(2)
    with t1:
        st.markdown('<div class="al-split-t" style="color:#D6333B">강한 쪽 (늘릴 후보)</div>', unsafe_allow_html=True)
        st.markdown(_tilt_table(a["tilt"]["strong"]), unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="al-split-t" style="color:#1F66C9">약한 쪽 (줄일 후보)</div>', unsafe_allow_html=True)
        st.markdown(_tilt_table(a["tilt"]["weak"]), unsafe_allow_html=True)
    reg = trend.rate_regime(snap["sm"])
    if reg:
        st.markdown(f'<div class="mc-legend">금리 국면 <b>{reg["name"]}</b> (20일: 2년물 {reg["d2"]:+.2f}%p, 10년물 {reg["d10"]:+.2f}%p) · '
                    f'과거 이 국면에 강했던 섹터(블로그 인용): {html.escape(reg["past"] or "표에 없음")}</div>', unsafe_allow_html=True)

    _analog_block()

    _sec("점수 흐름", "과거에 이 점수였을 때 지수는 어땠나")
    if h.empty:
        st.caption("과거 점수를 계산할 데이터가 부족해요.")
    else:
        st.plotly_chart(charts.score_history(h, alloc.BANDS), key="al_hist", config={"displaylogo": False})
        rows = []
        for r in alloc.band_stats(h):
            if not r["days"]:
                continue
            f = lambda v, w: "—" if v is None else f'{_p(v, 1)} <span style="color:#8A979F;font-size:.75rem">오른 날 {w:.0f}%</span>'
            rows.append([f'<b style="color:{r["color"]}">{r["band"]}</b> <span style="color:#8A979F">주식 {r["equity"]}</span>',
                         f'{r["days"]}일', f(r["kospi"], r["kospi_win"]), f(r["nasdaq"], r["nasdaq_win"])])
        st.markdown(_table(["점수 구간", "머문 날", "그 뒤 20일 코스피", "그 뒤 20일 나스닥"], rows), unsafe_allow_html=True)
        st.caption(f'{h["date"].iloc[0]:%Y-%m-%d}부터. 과거 점수는 하이일드·외국인 수급 없이 계산해요. 과거 결과가 미래를 보장하진 않아요.')

    if ai.api_key():
        with st.expander("🤖 AI 시황 해설 (API 요금 별도)"):
            _ai_block("market", ai.market_context(snap, trend.market_view(snap), issues.build(snap), reg), ai.MARKET_ASK,
                      "AI 해설 만들기")
    st.caption("점수는 규칙의 결과예요. 투자 권유가 아니에요.")


# ═══════════════════════════ 내 계좌 점검 ═══════════════════════════
@st.cache_data(ttl=15 * 60, show_spinner="보유 종목 시세를 받는 중이에요…")
def _holdings(codes: tuple[tuple[str, bool], ...]) -> dict:
    out = {}
    us = [c for c, kr in codes if not kr]
    if us:
        out |= {k: v for k, v in S.yahoo(us, period="1y").items() if v is not None and not v.empty}
    for c, kr in codes:
        if kr:
            df = S.naver(c, count=300)
            if df is not None and not df.empty:
                out[c] = df
    return out


def tab_account(snap: dict) -> None:
    _, fl = _flows()
    a = alloc.build(snap, fl)
    q = st.query_params.get("pf")
    left, right = st.columns([1, 2.2])
    with left:
        text = st.text_area("보유 종목과 비중(%)", value=portfolio.decode(q) if q else portfolio.EXAMPLE, height=190, key="pf_text",
                            help="한 줄에 하나: '삼성전자 30', '000660 20', 'NVDA 10', '현금 40'. 합이 100이 아니면 나머지는 현금으로 봐요.")
        enc = portfolio.encode(text)
        if enc and enc != q:
            st.query_params["pf"] = enc
        st.caption("주소창 주소를 즐겨찾기하면 다음에도 그대로 떠요. 입력은 이 브라우저 주소에만 남고 어디에도 저장되지 않아요.")
        with st.expander("이름으로 알아보는 종목"):
            st.caption(", ".join(sorted(portfolio.NAMES)) + ". 목록에 없으면 6자리 종목코드나 미국 티커를 적어 주세요.")
    rows, cash, bad = portfolio.parse(text)
    if bad:
        left.warning("못 알아본 줄: " + ", ".join(bad))
    if not rows:
        right.info("보유 종목을 적으면 점검해 드려요.")
        return
    px = dict(snap.get("px", {}))
    need = tuple((r["code"], r["kr"]) for r in rows if r["code"] not in px)
    if need:
        px |= _holdings(need)
    c = portfolio.check(rows, cash, px, snap, a)
    with right:
        b = c["band"]
        gap_txt = "권장 안" if c["gap"] == 0 else (f'{c["gap"]:+.0f}%p')
        gap_col = "#1D7A4C" if c["gap"] == 0 else (DOWN if c["gap"] > 0 else "#B7791F")
        kpis = [("주식 비중", f'{c["equity"]:.0f}%', f'현금 {c["cash"]:.0f}%', FLAT),
                ("권장(비중 판단)", b["equity"], f'{b["name"]} · {a["score"]:.0f}점', b["color"]),
                ("권장과 차이", gap_txt, "많으면 +, 적으면 −", gap_col),
                ("한국 : 미국", f'{c["kr_w"]:.0f} : {c["us_w"]:.0f}', f'신호 나눔 {c["split"]["kr"]} : {c["split"]["us"]}', FLAT),
                ("20일 계좌 기여", "—" if c["port_d20"] is None else f'{c["port_d20"]:+.1f}%', "보유 종목 20일 등락 × 비중", _c(c["port_d20"])),
                ("하루 흔들림", "—" if c["vol"] is None else f'±{c["vol"] * c["equity"] / 100:.1f}%', "최근 20일 표준편차 × 주식 비중", FLAT)]
        st.markdown('<div class="idx-row" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">' + "".join(
            f'<div class="idx"><div class="idx-name">{n}</div><div class="idx-val" style="color:{col}">{v}</div>'
            f'<div class="mc-legend" style="margin:2px 0 0">{html.escape(sub)}</div></div>' for n, v, sub, col in kpis) + "</div>",
            unsafe_allow_html=True)
        st.plotly_chart(charts.alloc_bars(c, rows), key="pf_bars", config={"displayModeBar": False})
        lv = {"good": UP, "warn": "#B7791F", "bad": DOWN}
        st.markdown('<div class="mc-sum">' + "".join(f'<div><span style="color:{lv[l]}">●</span> {html.escape(t)}</div>'
                                                    for l, t in portfolio.notes(c)) + "</div>", unsafe_allow_html=True)

    _sec("종목별 점검", "추세 · 점검선 · 금리/유가 민감도(과거 1년) · 블로그 규칙")
    body = []
    for it in c["items"]:
        if not it["ok"]:
            body.append([f'<b>{html.escape(it["name"])}</b>', f'{it["w"]:.0f}%', "—", "—", "—", "§시세를 받지 못했어요", "—", "—", "—", "—", "§"])
            continue
        col = trend.STAGE_COLOR.get(it["stage"].split("(")[0], FLAT)
        fmt = ",.0f" if it["last"] >= 1000 else ",.2f"
        line = f'{it["line_name"]} {it["line"]:{fmt}} ({_p(it["line_gap"], 1)})' if it["line"] else "—"
        br = "—" if it["beta_rate"] is None else _p(it["beta_rate"] * 10, 2)
        bo = "—" if it["beta_oil"] is None else _p(it["beta_oil"] * 5, 2)
        body.append([f'<b>{html.escape(it["name"])}</b> <span style="color:#8A979F;font-size:.75rem">{it["code"]}</span>',
                     f'{it["w"]:.0f}%', f'{it["last"]:{fmt}}', _p(it["d1"]), _p(it["d20"], 1),
                     f'§<span class="mc-chip" style="color:{col};border-color:{col}">{html.escape(it["stage"])}</span> 고점 대비 {_p(it["from_high"], 1)}',
                     line, br, bo, "—" if it["corr"] is None else f'{it["corr"]:.2f}', "§" + html.escape(it["rule"])])
    st.markdown(_table(["종목", "비중", "현재가", "1일", "20일", "추세", "점검선", "10년물 +10bp 날", "유가 +5% 날", "지수 상관", "규칙(블로그)"],
                       body), unsafe_allow_html=True)
    st.caption("점검선: 50일선 위 종목은 50일선(추세 중심선), 아래 종목은 10일선(하락 멈춤 확인). 민감도: 과거 1년 동안 그 요인이 움직인 날 "
               "종목이 평균 얼마나 움직였는지(한국 종목은 전날 밤 미국 금리·유가 기준). 지수 상관: 한국 종목은 코스피, 미국 종목은 나스닥과.")

    _sec("보유 종목 흐름", "최근 6개월 · 시작 = 100")
    ok = [it for it in c["items"] if it["ok"]]
    if ok:
        st.plotly_chart(charts.rebased([(it["name"], it["series"]) for it in ok]
                                       + [(n, alloc._close(snap.get("px", {}), *k)) for n, k in (("코스피", alloc.KR_IDX), ("나스닥", ("^IXIC",)))],
                                       126), key="pf_lines", config={"displaylogo": False})
    st.caption("숫자는 과거 시세로 계산한 사실이고, '규칙'은 보내 주신 블로그 기준을 그대로 적용한 결과예요. 투자 권유가 아니에요.")


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


TONE = {"good": UP, "warn": "#B7791F", "bad": DOWN, "info": "#6B7280"}


def _bench_for(group: str, sym: str) -> tuple[str | None, str]:
    """상대강도 기준: 한국 종목은 코스피, 미국 섹터·테마·종목은 S&P500(SPY), 지수는 없음."""
    if group == "한국 대장주":
        return "^KS11", "코스피"
    if group == "세계 지수":
        return (None, "") if sym == "^GSPC" else ("^GSPC", "S&P500")
    return ("SPY", "S&P500") if sym != "SPY" else (None, "")


def _read_html(r: dict | None, big: bool = False) -> str:
    if not r:
        return ""
    lines = "".join(f'<li><span style="color:{TONE[t]}">●</span> {html.escape(x)}</li>' for t, x in r["lines"])
    return (f'<div class="cr{" big" if big else ""}"><div class="cr-v" style="color:{TONE[r["tone"]]}">{html.escape(r["verdict"])}</div>'
            f'<ul>{lines}</ul></div>')


def tab_charts(snap: dict) -> None:
    px, tr, sm = snap.get("px", {}), snap.get("trend", {}), snap["sm"]
    groups = _groups()
    c1, c2 = st.columns([3, 2])
    g = _seg("묶음", list(groups), key="ch_group", where=c1)
    order = _seg("정렬", ["기본", "20일 강한 순", "추세 점수 순"], key="ch_order", where=c2)
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
        with cols[i % 3], st.container(border=True):
            stage = t["stage"] if t else "—"
            col = trend.STAGE_COLOR.get(stage, FLAT)
            last = f'{s["last"]:{_fmt_for(s["last"])}}' if s else "—"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:0">'
                f'<b>{html.escape(name)} <span style="color:#6B7A85;font-weight:400;font-size:.8rem">{html.escape(sym)}</span></b>'
                f'<span>{last} {_p(s and s["d1"])}</span></div>'
                f'<div style="font-size:.78rem;margin-bottom:-6px">'
                f'<span class="mc-chip" style="color:{col};border-color:{col}">{stage}</span> '
                f'20일 {_p(s and s["d20"], 1)} · 고점 대비 {_p(t and t["from_high"], 1)}</div>',
                unsafe_allow_html=True)
            st.plotly_chart(charts.mini(px[sym]), key=f"mini_{g}_{sym}", config={"displayModeBar": False, "staticPlot": True})
            bsym, bname = _bench_for(g, sym)
            st.markdown(_read_html(trend.chart_read(px[sym], px.get(bsym), bname)), unsafe_allow_html=True)

    _sec("크게 보기")
    d1, d2 = st.columns([3, 2])
    pick = d1.selectbox("종목·지수", items, format_func=lambda x: f"{x[1]} ({x[0]})", key=f"ch_pick_{g}")
    per = _seg("기간", list(charts.PERIODS), key="ch_per", where=d2, default="6개월")
    df = px.get(pick[0])
    if df is not None and len(df):
        st.plotly_chart(charts.candle(df, charts.PERIODS[per], fmt=_fmt_for(float(df["close"].iloc[-1]))),
                        key="big_chart", config={"displaylogo": False, "scrollZoom": True})
        bsym, bname = _bench_for(g, pick[0])
        st.markdown(_read_html(trend.chart_read(df, px.get(bsym), bname), big=True), unsafe_allow_html=True)


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
    _sec("미국 경제지표 한눈에")
    st.markdown(_table(["지표", "최근", "직전", "기준일", "1년 범위", "읽는 법"], rows), unsafe_allow_html=True)
    st.caption("FRED(세인트루이스 연준) 자료. CPI·PCE·산업생산은 전년 대비 %, 고용은 전월 대비 증감, 소매판매는 전월 대비 %예요.")

    _sec("지표 자세히 보기 + 발표일 각국 지수 반응")
    names = {e["name"]: e for e in C.ECON}
    pick = _seg("지표", list(names), key="ec_pick")
    e = names[pick]
    s = series.get(e["id"])
    if s is None or s.empty:
        st.info("이 지표를 받지 못했어요.")
        return
    span = _seg("기간", ["1년", "5년", "전체(약 12년)"], key="ec_span")
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
    _sec(f"🤖 {e['name']} 해석", "기사·리포트 검색")
    _ai_block(f"econ_{e['id']}", ai.indicator_context(e, summ.get(e["id"]), rel, stats, sahm), ai.INDICATOR_ASK,
              f"{e['name']} AI 해석 만들기")


# ═══════════════════════════ 세계 시황 해석(첫 탭) ═══════════════════════════
def _gist_chips(n: dict) -> str:
    if not n.get("ko"):
        return ""
    return '<div class="dg-ko">' + "".join(f"<span>{html.escape(w)}</span>" for w in n["ko"]) + "</div>"


def _claude_news() -> None:
    """Claude가 쓴 최신 해석 글의 '## 뉴스 해석' 부분."""
    reps = report.all_reports()
    if not reps:
        return
    sec = report.section(reps[0]["text"], "뉴스 해석")
    if sec:
        with st.container(border=True, key="rep_news"):
            st.markdown(f'<div class="dg-h">🧠 Claude 뉴스 해석 <span>{reps[0]["when"]} · 매일 오전 8시·밤 8시</span></div>',
                        unsafe_allow_html=True)
            st.markdown(sec)


def _digest_block(d: dict, cards: int = 8, items: int = 12) -> None:
    """핵심 뉴스 → 새로 뜬 뉴스 → 주제별 카드 → 목록."""
    if not d["news"]:
        st.caption("지난 24시간 관련 뉴스가 없어요.")
        return
    if d.get("lines"):
        st.markdown('<div class="mc-sum">' + "".join(f"<div>· {html.escape(x)}</div>" for x in d["lines"]) + "</div>",
                    unsafe_allow_html=True)
    rows = []
    for i, n in enumerate(d["top"], 1):
        when = n["when"].astimezone(S.KST).strftime("%m/%d %H:%M") if n.get("when") else ""
        rows.append(f'<div class="dg-row"><b class="dg-no">{i}</b><div><span class="dg-tp">{html.escape(digest.NAMES[n["topic"]])}</span>'
                    f'<a href="{html.escape(n["url"])}" target="_blank">{html.escape(n["title"])}</a>'
                    f'<span class="dg-m"> · {n["n"]}곳 보도{" · 주요 외신 " + html.escape(", ".join(n["major"][:3])) if n.get("major") else ""} · {when}</span>'
                    f'{_gist_chips(n)}</div></div>')
    st.markdown('<div class="mc-card dg"><div class="dg-h">지금 가장 크게 보도된 뉴스 5 <span>언론사 수·주요 외신·최신순</span></div>'
                + "".join(rows) + "</div>", unsafe_allow_html=True)
    if d["new"]:
        st.markdown('<div class="mc-legend"><b>🆕 최근 3시간 새로 뜬 뉴스</b> · ' + " · ".join(
            f'<a href="{html.escape(n["url"])}" target="_blank">{html.escape(n["title"])}</a> ({n["n"]}곳)' for n in d["new"]) + "</div>",
            unsafe_allow_html=True)
    tops = d["topics"][:cards]
    st.markdown('<div class="idx-row" style="grid-template-columns:repeat(auto-fill,minmax(240px,1fr))">' + "".join(
        f'<div class="idx dg-card"><div class="idx-name"><b>{html.escape(t["name"])}</b> <small>{t["n"]}건 · 교차확인 {t["n_cross"]}</small></div>'
        f'<div class="dg-t"><a href="{html.escape(t["news"][0]["url"])}" target="_blank">{html.escape(t["news"][0]["title"])}</a></div>'
        f'{_gist_chips(t["news"][0])}'
        + (f'<div class="dg-mv">{" · ".join(f"{html.escape(a)} 5일 {html.escape(b)}" for a, b in t["moves"])}</div>' if t["moves"] else "")
        + (f'<div class="dg-path">{html.escape(t["path"])}</div>' if t["path"] else "") + "</div>" for t in tops) + "</div>",
        unsafe_allow_html=True)
    if not items:
        return
    with st.expander(f"뉴스 목록 {len(d['news'])}건 (주제·중요도 순)"):
        for n in sorted(d["news"], key=lambda n: (digest.FACT.count(n["status"]) == 0, -n["w"]))[:items]:
            when = n["when"].astimezone(S.KST).strftime("%m/%d %H:%M") if n.get("when") else ""
            st.markdown(f'<div class="mc-news">{_chip(n["status"])} <span class="dg-tp">{html.escape(digest.NAMES[n["topic"]])}</span>'
                        f'<span class="m">{when}</span><div class="h"><a href="{html.escape(n["url"])}" target="_blank">'
                        f'{html.escape(n["title"])}</a></div>{_gist_chips(n)}'
                        f'<div class="m">{html.escape(", ".join(n["sources"][:8]))}</div></div>', unsafe_allow_html=True)


def tab_world(snap: dict) -> None:
    reps = report.all_reports()
    if reps:
        pick = reps[0]
        if len(reps) > 1:
            choice = st.selectbox("해석 글", reps, format_func=lambda r: f'{r["when"]} · {r["title"]}', key="rep_pick")
            pick = choice or reps[0]
        st.markdown(f'<div class="rep"><div class="rep-top"><span class="brand-tag">🌐 세계 시황 해석</span>'
                    f'<span class="mc-legend" style="margin:0">{pick["when"]} (한국시간) · 매일 오전 8시·밤 8시</span></div>'
                    f'<div class="rep-t">{html.escape(pick["title"])}</div>'
                    + (f'<div class="rep-lead">{html.escape(pick["lead"])}</div>' if pick["lead"] else "") + "</div>",
                    unsafe_allow_html=True)
        with st.container(border=True, key="rep_body"):
            st.markdown("\n".join(l for l in report.body(pick["text"]).splitlines() if not l.startswith(">")))
        st.caption("Claude가 지수·수급·외신을 출처 2곳 이상 맞춰 보고 쓴 글이에요. [사실]은 숫자·보도, [해석]은 Claude의 판단, "
                   "[블로그 관점]은 보내 주신 사진의 관점이에요. 투자 권유가 아니에요.")
    else:
        st.info("아직 해석 글이 없어요. 매일 오전 8시·밤 8시에 자동으로 올라와요.")

    iss = {x["key"]: x for x in issues.build(snap)}
    _sec("유가 · 중동", "지금 숫자(실시간 데이터)")
    keys = [("CL=F", "WTI", "idx"), ("BZ=F", "브렌트", "idx"), ("^OVX", "OVX(유가 변동성)", "idx"), ("GC=F", "금", "idx"),
            ("DX-Y.NYB", "달러인덱스", "idx"), ("fred:DGS10", "미 10년물", "rate")]
    st.markdown('<div class="idx-row">' + "".join(_kpi(snap, *k) for k in keys) + "</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([3, 2])
    with c1:
        df = snap.get("px", {}).get("CL=F")
        if df is not None and len(df):
            st.plotly_chart(charts.candle(df, 126, show_vol=False, height=380), key="oil_chart",
                            config={"displaylogo": False})
            t = snap.get("trend", {}).get("CL=F")
            if t:
                st.caption(f"WTI {t['stage']}: {t['comment']}")
    with c2:
        oil = iss.get("oil")
        if oil:
            st.markdown(f'<div class="mc-sum"><b>유가가 움직이면 무엇이 같이 움직였나 (5일)</b><br>{html.escape(oil["comment"])}</div>',
                        unsafe_allow_html=True)
            rows = [[html.escape(l["name"]), "같이" if l["how"] == "same" else "반대", l["move"],
                     "—" if l["ok"] is None else ("✔" if l["ok"] else "✘")] for l in oil["links"]]
            st.markdown(_table(["섹터·지표", "가설", "5일", "맞음"], rows), unsafe_allow_html=True)

    _sec("전쟁 · 지정학 · 유가 뉴스 요약", "새 뉴스가 들어오면 15분마다 다시 정리")
    _digest_block(digest.build(snap, only=digest.GEO_KEYS), cards=5, items=20)

    _sec("세계 지수 한눈에", "1일 · 5일 등락")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_bars([(f'{i["region"]} {i["name"]}', (snap["sm"].get(i["yf"]) or {}).get("d1")) for i in C.INDICES]),
                    unsafe_allow_html=True)
    with c2:
        st.markdown(_bars([(f'{i["region"]} {i["name"]}', (snap["sm"].get(i["yf"]) or {}).get("d5")) for i in C.INDICES]),
                    unsafe_allow_html=True)


# ═══════════════════════════ 수급(네이버) ═══════════════════════════
@st.cache_data(ttl=10 * 60, show_spinner="수급을 받는 중이에요…")
def _flows() -> tuple[dict, dict]:
    ov = flows.fetch_market_overview()
    return ov, flows.fetch_investor_flows(ov)


def _eok(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f'<span style="color:{_c(v)}">{v:+,.0f}억</span>'


def tab_flows(snap: dict) -> None:
    ov, fl = _flows()
    _sec("오늘 코스피 · 코스닥", "네이버 증권(밸류체인 신고가 보드와 같은 출처)")
    cards = []
    for mk in ("코스피", "코스닥"):
        o = ov.get(mk) or {}
        d, b = o.get("deal") or {}, o.get("breadth") or {}
        rate = o.get("rate")
        cards.append(
            f'<div class="idx"><div class="idx-name">{mk}<small>{html.escape(str(o.get("status") or ""))}</small></div>'
            f'<div class="idx-val">{(o.get("last") or 0):,.2f}</div>'
            + (f'<span class="idx-chg" style="color:{_c(rate)}">{rate:+.2f}%</span>' if rate is not None else "")
            + f'<div style="font-size:.8rem;margin-top:.3rem">외국인 {_eok(d.get("외국인"))} · 기관 {_eok(d.get("기관"))} · '
              f'개인 {_eok(d.get("개인"))}<br>프로그램 {_eok(o.get("program"))} · 상승 {b.get("상승") or "—"} / 하락 {b.get("하락") or "—"}</div></div>')
    st.markdown('<div class="idx-row" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">' + "".join(cards) + "</div>",
                unsafe_allow_html=True)
    for mk in ("코스피", "코스닥"):
        df = fl.get(mk)
        if df is None or df.empty:
            st.info(f"{mk} 일별 수급을 받지 못했어요.")
            continue
        _sec(f"{mk} 투자자별 순매수", "최근 20거래일 · 억원")
        d = df.tail(20).iloc[::-1]
        rows = [["최근 5일 합계"] + [_eok(df.tail(5)[k].sum()) for k in flows.INVESTORS]
                + [_eok(df.tail(5)[k].sum()) if df[k].notna().any() else "—" for k in ("금융투자", "투신(사모)", "연기금")],
                ["최근 20일 합계"] + [_eok(df.tail(20)[k].sum()) for k in flows.INVESTORS]
                + [_eok(df.tail(20)[k].sum()) if df[k].notna().any() else "—" for k in ("금융투자", "투신(사모)", "연기금")]]
        rows += [[f'{r["date"]:%m/%d}'] + [_eok(r[k]) for k in flows.INVESTORS + ["금융투자", "투신(사모)", "연기금"]]
                 for _, r in d.iterrows()]
        st.markdown(_table(["날짜", "개인", "외국인", "기관", "금융투자", "투신", "연기금"], rows), unsafe_allow_html=True)
    st.caption("외국인·기관이 같이 사는 날이 이어지면 수급이 받쳐 주는 구간, 개인만 사는 날이 이어지면 수급이 약한 구간으로 봐요(블로그 관점).")


# ═══════════════════════════ 상관관계 ═══════════════════════════
@st.cache_data(ttl=3600, show_spinner="10년치 지수를 받는 중이에요…")
def _long() -> dict:
    return corr.fetch_long()


def _corr_cell(s: dict | None) -> str:
    if not s or s.get("corr") is None:
        return "—"
    c = s["corr"]
    col = UP if c >= 0.5 else ("#E0672B" if c >= 0.3 else FLAT)
    return (f'<b style="color:{col}">{c:.2f}</b><br><span style="font-size:.72rem;color:#6B7A85">'
            f'{corr.read(c)} · β {s["beta"]:.2f}</span>')


def tab_corr(snap: dict) -> None:
    px = _long()
    if len(px) < 2:
        st.info("지수 장기 데이터를 받지 못했어요.")
        return
    _sec("기간별 상관계수", "일간 등락률 기준 · β = 나스닥(기준) 1% 움직일 때 대상이 움직인 %")
    rows = []
    for r in corr.table(px):
        rows.append([html.escape(r["pair"])] + [_corr_cell(r["cells"].get(n)) for n, _ in corr.WINDOWS])
    st.markdown(_table(["비교"] + [n for n, _ in corr.WINDOWS], rows), unsafe_allow_html=True)
    st.caption("상관계수: 1이면 완전히 같이, 0이면 무관, −1이면 반대로 움직여요. 미국 장은 한국 장이 끝난 뒤에 열리니 "
               "'전날 밤 나스닥 → 오늘 코스피'가 실제 영향을 더 잘 보여 줘요. 0.5 이상 강함, 0.3~0.5 보통.")

    _sec("최근 1~3일 · 1주 · 1달", "같은 방향이었던 날 수 · 누적 등락")
    rows = []
    for b, t, lag in corr.PAIRS[:2] + corr.PAIRS[4:]:
        if b not in px or t not in px:
            continue
        m = corr.align(px[b], px[t], lag)
        cells = []
        for name, n in corr.RECENT:
            s = corr.stats(m.tail(n))
            if not s:
                cells.append("—")
                continue
            extra = f'<br><span style="font-size:.72rem">계수 {s["corr"]:.2f}</span>' if s.get("corr") is not None else ""
            cells.append(f'{s["same"]}/{s["n"]}일 같은 방향<br>{_p(s["base_cum"], 1)} vs {_p(s["tgt_cum"], 1)}{extra}')
        rows.append([html.escape(f"{b} → {t}" + (" (전날 밤 → 오늘)" if lag else " (같은 날)"))] + cells)
    st.markdown(_table(["비교"] + [n for n, _ in corr.RECENT], rows), unsafe_allow_html=True)

    _sec("날짜별 나란히 보기", "최근 21거래일 · 한국 날짜 기준")
    rd = corr.recent_days(px)
    if not rd.empty:
        body = []
        for _, r in rd.iterrows():
            nq, ks = r["나스닥(전날 밤)"], r["코스피"]
            kq = r.get("코스닥")
            same = (nq > 0) == (ks > 0)
            body.append([f'{r["date"]:%m/%d}', f'{r["bdate"]:%m/%d} {_p(nq)}', _p(ks), _p(kq),
                         '<span style="color:#1D7A4C">같은 방향</span>' if same else '<span style="color:#B7791F">엇갈림</span>'])
        st.markdown(_table(["한국 날짜", "전날 밤 나스닥", "코스피", "코스닥", "나스닥↔코스피"], body), unsafe_allow_html=True)

    _sec("상관계수 흐름", "60거래일 이동 상관계수")
    pair = _seg("비교", ["나스닥 → 코스피", "나스닥 → 코스닥", "코스피 ↔ 코스닥"], key="corr_pair")
    b, t, lag = {"나스닥 → 코스피": ("나스닥", "코스피", True), "나스닥 → 코스닥": ("나스닥", "코스닥", True),
                 "코스피 ↔ 코스닥": ("코스피", "코스닥", False)}[pair]
    rl = corr.rolling(px, b, t, lag)
    if not rl.empty:
        st.plotly_chart(charts.line(rl, f"{pair} 60일 상관계수", height=300, zero=True), key="corr_roll",
                        config={"displaylogo": False})
        last = rl["value"].iloc[-1]
        avg = rl["value"].mean()
        st.caption(f"지금 {last:.2f} · 전체 기간 평균 {avg:.2f} — "
                   + ("평소보다 더 같이 움직이는 중(미국 영향이 커진 구간)" if last > avg + 0.1 else
                      "평소보다 덜 같이 움직이는 중(한국만의 재료·수급이 큰 구간)" if last < avg - 0.1 else "평소 수준이에요"))


def data_status() -> None:
    """화면 맨 아래: 출처별로 받았는지/못 받았는지."""
    if not S.STATUS:
        return
    with st.expander("🔧 데이터 상태 (빈칸이 보이면 여기를 캡처해 주세요)"):
        rows = [[html.escape(k), '<span style="color:#1D7A4C">받음</span>' if ok else '<span style="color:#C53030">실패</span>',
                 html.escape(msg), t] for k, (ok, msg, t) in sorted(S.STATUS.items())]
        st.markdown(_table(["출처", "상태", "설명", "시각"], rows), unsafe_allow_html=True)
