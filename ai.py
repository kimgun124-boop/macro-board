"""AI 해설(Claude). 대시보드 숫자 + 뉴스 + knowledge.md(보내 주신 이미지 정리)를 주고,
외신·리포트를 웹 검색으로 직접 확인해서 사실과 해석을 나눠 써 달라고 해요.

키: Streamlit secrets 또는 환경변수 ANTHROPIC_API_KEY. 없으면 버튼만 보이고 호출하지 않아요.
"""
from __future__ import annotations

import os
from pathlib import Path

import config as C
import issues as I

MODEL = "claude-opus-5-5"
KNOWLEDGE = (Path(__file__).parent / "knowledge.md").read_text(encoding="utf-8")
# 사실 확인에 쓸 언론사·기관(웹 검색 범위)
DOMAINS = ["reuters.com", "bloomberg.com", "nytimes.com", "wsj.com", "ft.com", "economist.com", "apnews.com",
           "cnbc.com", "marketwatch.com", "barrons.com", "bls.gov", "bea.gov", "federalreserve.gov",
           "stlouisfed.org", "yna.co.kr", "hankyung.com", "mk.co.kr", "asia.nikkei.com"]

RULES = """당신은 한국 개인투자자를 돕는 매크로 시황 해설가예요. 쉬운 한국어로, 짧은 문장으로 써요.

규칙
- 대시보드 숫자를 '사실'로 쓰고, 뉴스는 웹 검색으로 원문(외신·공식 발표)을 확인한 것만 사실로 써요.
- 같은 사건을 다르게 보도한 매체가 있으면 비교해서 어디가 무엇을 다르게 말했는지 적어요.
- 확인 못 한 내용은 '미확인', 해석은 '해석', 블로그 관점(아래 지식 노트)은 '블로그 관점'이라고 표시해요.
- 지식 노트는 해석 틀로만 써요. 노트의 과거 숫자를 오늘 사실처럼 쓰지 않아요.
- 특정 종목 매수·매도 지시는 하지 않아요. 추세추종 규칙상 어떤 구간인지는 말해도 돼요.
- 마크다운 소제목(####)과 짧은 목록을 써요. 전체 길이는 화면 한두 장.

아래는 사용자가 보내 준 블로그·리포트 이미지를 정리한 지식 노트예요.

"""


def api_key() -> str | None:
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    try:
        import streamlit as st
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def _fmt(v, d=2, pct=True):
    return "—" if v is None else (f"{v:+.{d}f}%" if pct else f"{v:.{d}f}")


def market_context(snap: dict, view: dict, iss: list[dict], regime: dict | None) -> str:
    sm, tr = snap["sm"], snap.get("trend", {})
    L = [f"기준 시각(한국): {snap['at']:%Y-%m-%d %H:%M}", "", "[지수] 이름: 종가, 1일, 5일, 20일, 추세 단계, 고점 대비"]
    for i in C.INDICES:
        s, t = sm.get(i["yf"]), tr.get(i["yf"])
        if s:
            L.append(f"- {i['name']}: {s['last']:,.2f}, {_fmt(s['d1'])}, {_fmt(s['d5'])}, {_fmt(s['d20'])}, "
                     f"{t['stage'] if t else '—'}, {_fmt(t and t['from_high'], 1)}")
    L.append("\n[금리·환율·원자재] 이름: 값, 1일 변화, 20일 변화")
    for m in C.MACRO:
        s = sm.get(m["yf"] or "fred:" + m["fred"])
        if s:
            if m["kind"] == "rate":
                L.append(f"- {m['name']}: {s['last']:.3f}%, {s.get('a1') or 0:+.3f}%p, {s.get('a20') or 0:+.3f}%p")
            else:
                L.append(f"- {m['name']}: {s['last']:,.2f}, {_fmt(s['d1'])}, {_fmt(s['d20'])}")
    L.append("\n[위험 지표]")
    for v in C.VOL:
        s = sm.get(v["yf"])
        if s:
            L.append(f"- {v['name']}: {s['last']:.2f} (1일 {_fmt(s['d1'])})")
    for f in C.FRED:
        s = snap["fred"].get(f["id"])
        if s:
            L.append(f"- {f['name']}: {s['last']:.2f}% (20일 {s.get('a20') or 0:+.2f}%p)")
    L.append("\n[섹터·테마 ETF] 티커 이름: 1일, 5일, 20일, 추세 단계")
    for sym, n in C.SECTORS + C.THEMES:
        s, t = sm.get(sym), tr.get(sym)
        if s:
            L.append(f"- {sym} {n}: {_fmt(s['d1'])}, {_fmt(s['d5'])}, {_fmt(s['d20'])}, {t['stage'] if t else '—'}")
    L.append("\n[한국 대장주] 이름: 1일, 20일, 추세 단계")
    for c, n, _ in C.KR_LEADERS:
        s, t = sm.get(c), tr.get(c)
        if s:
            L.append(f"- {n}: {_fmt(s['d1'])}, {_fmt(s['d20'])}, {t['stage'] if t else '—'}")
    L.append(f"\n[추세추종 점검 결과] 판단: {view['verdict']} (점수 {view['score']})")
    L += [f"- ({x['level']}) {x['text']}" for x in view["lines"]]
    if regime:
        L.append(f"\n[금리 국면] {regime['name']} (2년물 20일 {regime['d2']:+.2f}%p, 10년물 {regime['d10']:+.2f}%p)")
    L.append("\n[이슈별 5일 반응] 이슈: 지표 변화 / 관련 섹터(가설 방향, 실제, 맞음 여부) / 뉴스")
    for x in iss:
        links = "; ".join(f"{l['name']}({'같이' if l['how'] == 'same' else '반대'}, {l['move']}, "
                          f"{'맞음' if l['ok'] else ('틀림' if l['ok'] is False else '—')})" for l in x["links"])
        heads = " | ".join(f"[{n['status']}] {n['title']} ({', '.join(n['sources'][:3])})" for n in x["news"][:4])
        L.append(f"- {x['name']}: {', '.join(f'{a} {b}' for a, b in x['drivers'])} / {links} / {heads or '뉴스 없음'}")
    L.append("\n[지난 24시간 주요 뉴스 제목(자동 분류)]")
    for n in (snap.get("news") or [])[:30]:
        L.append(f"- [{n['status']}] {n['title']} — {', '.join(n['sources'][:4])} {n['url']}")
    return "\n".join(L)


MARKET_ASK = """위 대시보드 데이터로 오늘 시황을 해설해 주세요.

1. #### 한 줄 요약: 오늘 시장을 움직인 가장 큰 힘 하나.
2. #### 이슈와 섹터 반응: 오늘 큰 이슈 2~4개마다
   - 무슨 일(사실): 웹 검색으로 외신(NYT, WSJ, FT, Reuters, Bloomberg 등) 원문을 확인하고, 매체 간 차이를 비교해요.
   - 시장 반응(사실): 위 숫자로 어떤 섹터가 어떻게 움직였는지 말해요.
   - 해석: 가설대로 움직였는지, 아니라면 왜인지 말해요.
3. #### 추세추종으로 본 진입 판단: 점검 결과를 쉬운 말로 풀어요. 무엇을 확인하면 판단이 바뀌는지도 적어요.
4. #### 블로그 관점과 비교: 지식 노트의 틀과 오늘 데이터가 맞는 점과 다른 점을 적어요.
5. #### 다음에 볼 것: 일정이나 지표 3개 이내."""


def _react(v, sym: str) -> str:
    if v is None:
        return "—"
    return f"{v:+.3f}%p" if sym == "^TNX" else f"{v:+.2f}%"


def indicator_context(e: dict, summ: dict | None, rel: dict, stats: list[dict], sahm: float | None) -> str:
    L = [f"지표: {e['name']} (FRED {e['id']}, 변환 {e['how']}, 단위 {e['unit']})"]
    if summ:
        L.append(f"최근 값 {summ['last']:.2f} (기준 {summ['date']:%Y-%m}), 직전 {summ['prev']:.2f}, "
                 f"1년 범위 {summ['y_lo']:.2f}~{summ['y_hi']:.2f}")
    if sahm is not None:
        L.append(f"삼의 법칙 값 {sahm:.2f}%p (0.5 이상이면 침체 신호)")
    L.append("발표일 " + ("(FRED 발표 일정)" if rel["exact"] else "(규칙으로 추정한 날짜)"))
    L.append("최근 발표: 기준월, 발표일, 값, 직전(또는 비교 기준), 직전 대비 뜨거움/식음, 지수 반응(아시아는 다음 거래일)")
    for r in rel["rows"]:
        rx = ", ".join(f"{n} {_react(r['react'][s], s)}" for s, n, _ in C.REACT)
        L.append(f"- {r['ref']:%Y-%m}, {r['day']:%Y-%m-%d}, {r['value']:.2f}, {r['base']:.2f}, "
                 f"{'뜨거움' if r['hot'] else '식음'}, {rx}")
    L.append("뜨거울 때 / 식을 때 평균 반응")
    for s in stats:
        L.append(f"- {s['name']}: {_fmt(s['hot'])} (n={s['n_hot']}) / {_fmt(s['cool'])} (n={s['n_cool']})")
    return "\n".join(L)


INDICATOR_ASK = """위 데이터는 이 경제지표의 최근 발표와 발표일 각국 지수 반응이에요.

1. #### 이번 발표 해석: 웹 검색으로 최근 발표를 다룬 기사·리포트를 찾아요(Reuters, Bloomberg, WSJ, NYT, CNBC, 발표 기관, 연준 발언 등).
   - 시장 예상치(컨센서스)와 실제를 비교해요.
   - 세부 항목(예: 근원·서비스·주거비, 임금, 참가율, 수정치)에서 무엇이 핵심이었는지 적어요.
   - 매체마다 해석이 다르면 비교해요. 출처를 꼭 달아요.
2. #### 시장은 어떻게 받아들였나: 위 반응표로 미국, 유럽, 아시아(한국, 일본, 대만) 지수와 금리, 달러가 어떻게 움직였는지 적어요. 예상과 다르게 움직였으면 왜인지(기사 근거 또는 '해석' 표시) 적어요.
3. #### 패턴: 뜨거울 때와 식을 때의 평균 반응 차이와 표본 수의 한계를 적어요. 최근 시장이 '좋은 뉴스 = 나쁜 뉴스' 국면인지도 판단해요.
4. #### 읽는 법: 이 지표를 볼 때 초보자가 확인할 2~3가지.
5. #### 다음 발표 때 볼 것."""


def ask(context: str, question: str, effort: str = "medium") -> dict:
    """{text, sources, error}. 웹 검색 결과 링크는 sources에 모아요."""
    key = api_key()
    if not key:
        return {"text": "", "sources": [], "error": "ANTHROPIC_API_KEY가 없어요. Streamlit 설정의 Secrets에 넣어 주세요."}
    try:
        import anthropic
    except ImportError:
        return {"text": "", "sources": [], "error": "anthropic 패키지가 설치되지 않았어요."}
    client = anthropic.Anthropic(api_key=key)
    system = [{"type": "text", "text": RULES + KNOWLEDGE, "cache_control": {"type": "ephemeral"}}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8, "allowed_domains": DOMAINS}]
    messages = [{"role": "user", "content": f"<dashboard>\n{context}\n</dashboard>\n\n{question}"}]
    try:
        msg = None
        for _ in range(4):          # 웹 검색이 길어지면 pause_turn으로 멈춰요 → 이어서 요청
            with client.beta.messages.stream(
                model=MODEL, max_tokens=16000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                thinking={"type": "adaptive"}, output_config={"effort": effort},
                system=system, tools=tools, messages=messages,
            ) as stream:
                msg = stream.get_final_message()
            if msg.stop_reason != "pause_turn":
                break
            messages = messages[:1] + [{"role": "assistant", "content": msg.content}]
    except anthropic.AuthenticationError:
        return {"text": "", "sources": [], "error": "API 키가 맞지 않아요."}
    except anthropic.RateLimitError:
        return {"text": "", "sources": [], "error": "요청이 많아 잠시 막혔어요. 1분 뒤 다시 눌러 주세요."}
    except anthropic.APIStatusError as e:
        return {"text": "", "sources": [], "error": f"AI 서버 오류({e.status_code})예요. 잠시 뒤 다시 시도해 주세요."}
    except anthropic.APIConnectionError:
        return {"text": "", "sources": [], "error": "AI 서버에 연결하지 못했어요."}
    if msg.stop_reason == "refusal":
        return {"text": "", "sources": [], "error": "AI가 이 요청에 답하지 않았어요. 다시 시도해 주세요."}
    text, sources = [], {}
    for b in msg.content:
        if b.type == "text":
            text.append(b.text)
            for c in getattr(b, "citations", None) or []:
                url = getattr(c, "url", None)
                if url:
                    sources[url] = getattr(c, "title", None) or url
    return {"text": "".join(text).strip(), "sources": list(sources.items()), "error": None}


def market(snap: dict, view: dict, regime: dict | None) -> dict:
    return ask(market_context(snap, view, I.build(snap), regime), MARKET_ASK)


def indicator(e: dict, summ, rel, stats, sahm) -> dict:
    return ask(indicator_context(e, summ, rel, stats, sahm), INDICATOR_ASK)
