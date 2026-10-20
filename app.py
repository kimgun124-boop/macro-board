"""🌍 매크로 시황 보드 — 실행: streamlit run app.py   (인터넷 없이 확인: MACRO_MOCK=1 streamlit run app.py)

새 화면을 넣고 싶으면 view.py에 tab_무엇() 함수를 만들고 아래 TABS에 한 줄 추가하면 돼요.
"""
import streamlit as st

import macro
import view

st.set_page_config(page_title="매크로 시황 보드", page_icon="🌍", layout="wide")

TABS = [
    ("📊 지수·금리·위험", view.tab_markets),
    ("🏭 섹터·대장주", view.tab_sectors),
    ("📰 사실 필터 뉴스", view.tab_news),
]


@st.cache_data(ttl=15 * 60, show_spinner="시세와 뉴스를 모으는 중이에요(30초 안팎)…")
def load() -> dict:
    return macro.snapshot()


top = st.columns([6, 1])
top[0].title("🌍 매크로 시황 보드")
if top[1].button("새로고침", use_container_width=True):
    load.clear()

snap = load()
view.header(snap)
for tab, (_, draw) in zip(st.tabs([name for name, _ in TABS]), TABS):
    with tab:
        draw(snap)
st.caption("숫자와 사실만 모았어요. 전망·추천은 넣지 않아요. 15분마다 새로 받아요.")
