"""Common application frame and safe read feedback."""
from html import escape
from pathlib import Path

import streamlit as st

from domain.presenters import time_label
from services.gateway import Gateway
from state import read


def panel(key: str):
    """Style only our explicit container keys via Streamlit's documented CSS hook."""
    return st.container(border=True, key=f"sews_panel_{key}")


def heading(title: str, description: str = "") -> None:
    st.html(f'<h1 class="sews-title">{escape(title)}</h1>')
    if description:
        st.caption(description)


def read_feedback(key: str, result) -> bool:
    """Return whether the displayed response is fresh enough for actions."""
    error = st.session_state.read_errors.get(key)
    if error:
        st.error(error)
        if result is not None:
            st.warning(f"과거 데이터 · 마지막 성공 조회 {time_label(result.as_of, True)} KST")
    return result is not None and not error


def render_shell(gateway: Gateway, demo: bool, pages: dict) -> None:
    st.html(f"<style>{(Path(__file__).parents[1] / 'ui/styles.css').read_text()}</style>")
    health = read(st.session_state, "health", gateway.get_health)
    if demo:
        connection, user = "● 합성 데이터 · 실제 모델 미연결", "데모 사용자"
    elif st.session_state.read_errors.get("health") or health is None:
        connection, user = "○ 연결 확인 실패", "서버 권한 기준"
    elif health.status == "ok" and health.model_ready:
        connection, user = f"● 연결 정상 · {time_label(health.checked_at)} 확인", "서버 권한 기준"
    else:
        connection, user = "△ 서버 응답 · 모델 미준비", "서버 권한 기준"
    st.html(f'<div class="sews-header"><span class="sews-brand">SEWS</span>'
            '<span class="sews-context">ICU 조기 경보</span><span>ICU-A</span>'
            f'<span class="sews-status">{escape(connection)}</span>'
            f'<span class="sews-status">{escape(user)}</span></div>')
    with st.sidebar:
        st.html('<p class="sews-brand">SEWS</p>')
        st.caption("CLINICAL")
        st.page_link(pages["monitor"], label="통합 모니터", icon=":material/dashboard:")
        st.page_link(pages["alerts"], label="경보 이력", icon=":material/notifications:")
        st.divider()
        st.caption("ICU-A · 관찰 중")
        st.caption("24시간 관찰\n\n향후 6시간 위험 평가")
        st.toggle("간결 보기", key="compact", help="태블릿에서는 표 열을 줄이고 상세 정보를 세로로 표시합니다.")
        st.toggle("모니터 자동 갱신 (30초)", key="auto_refresh")
        if st.button("연결 상태 다시 확인", width="stretch"):
            read(st.session_state, "health", gateway.get_health, refresh=True)
            st.rerun()
        st.caption("합성 데이터 · 세션 내 가상 저장" if demo else "API 데이터 · 서버 저장")
    if demo:
        st.caption("DEMO · 모든 환자·관측·점수·설명은 합성 데이터입니다. 기록은 현재 세션에만 보관됩니다.")
    st.caption("연구용 프로토타입 · 모델 점수는 발생 확률이나 진단을 의미하지 않습니다.")
