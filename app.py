"""🌍 매크로 시황 보드 — 실행: streamlit run app.py   (인터넷 없이 확인: MACRO_MOCK=1 streamlit run app.py)

새 화면을 넣고 싶으면 view.py에 tab_무엇() 함수를 만들고 아래 TABS에 한 줄 추가하면 돼요.
디자인은 밸류체인 신고가 보드(very)의 theme.py를 그대로 써요.
"""
import time

import streamlit as st

try:
    import macro
    import theme
    import view
except KeyError:
    # 저장소가 바뀐 직후 스트림릿이 바뀐 파일을 다시 읽는 순간과 겹치면 가끔 KeyError가 나요.
    # 잠깐 쉬었다 다시 실행하면 풀려요. 세 번 넘게 나면 앱 관리 화면에서 Reboot을 눌러야 해요.
    n = st.session_state.get("_import_retry", 0)
    if n < 3:
        st.session_state["_import_retry"] = n + 1
        time.sleep(1.5)
        st.rerun()
    st.error("코드를 새로 불러오는 중에 문제가 생겼어요. 오른쪽 아래 'Manage app' → ⋮ → 'Reboot app'을 눌러 주세요.")
    st.stop()

st.set_page_config(page_title="매크로 시황 보드", page_icon="🌍", layout="wide")

# 탭 묶음: 1~5 판단·해석 · 6~8 시장 데이터 · 9~11 수급·지표 (묶음 색은 theme.py)
TABS = [
    ("🎯 비중 판단", view.tab_alloc),
    ("🧾 내 계좌", view.tab_account),
    ("🌐 세계 시황 해석", view.tab_world),
    ("📈 차트 보드", view.tab_charts),
    ("🔗 이슈 ↔ 섹터", view.tab_issues),
    ("📊 지수·금리·위험", view.tab_markets),
    ("🏭 섹터·대장주", view.tab_sectors),
    ("📰 사실 필터 뉴스", view.tab_news),
    ("💰 수급", view.tab_flows),
    ("🔀 상관관계", view.tab_corr),
    ("📅 경제지표", view.tab_econ),
]


@st.cache_data(ttl=15 * 60, show_spinner="시세와 뉴스를 모으는 중이에요(30초 안팎)…")
def load() -> dict:
    return macro.snapshot()


st.markdown(view.CSS, unsafe_allow_html=True)
theme.apply()    # 🎨 very와 같은 디자인(색·카드·글꼴)
top = st.columns([6, 1], vertical_alignment="center")
with top[0]:
    theme.header("매크로 시황 보드", "사실(지수·금리·수급·외신)로 계좌 비중을 정해요 · 상승 빨강, 하락 파랑", "MACRO")
if top[1].button("새로고침", use_container_width=True):
    load.clear()

snap = load()
st.markdown(f'<div class="status">{snap["at"]:%m/%d %H:%M} 기준 · 시세 15분마다 갱신 · 해석 글 매일 오전 8시·밤 8시</div>',
            unsafe_allow_html=True)
view.header(snap)
with st.container(key="main_tabs"):
    for tab, (_, draw) in zip(st.tabs([name for name, _ in TABS]), TABS):
        with tab:
            draw(snap)
view.data_status()
st.caption("숫자는 사실, 판단·해석 글은 해석이에요(투자 권유 아님).")
