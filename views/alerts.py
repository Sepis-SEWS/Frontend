"""Alert history with server-side filters and independent acknowledgement/records."""
from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

from components.care_form import care_form
from components.layout import heading, read_feedback
from components.summary import alert_summary
from domain.presenters import KST, score_label, time_label
from state import read

heading("경보 이력", "경보 발생과 확인, 평가·조치 기록을 확인합니다.")
gateway = st.session_state.gateway
refresh = st.button("경보 목록 갱신", icon=":material/refresh:")
left, right = st.columns(2)
with left:
    period = st.selectbox("조회 기간", ["오늘", "최근 7일", "전체"], key="alert_period")
    query = st.text_input("환자·병상 검색", key="alert_query")
with right:
    status = st.selectbox("확인 상태", [None, "unacknowledged", "acknowledged"], key="alert_status",
                          format_func=lambda x: {None: "전체", "unacknowledged": "미확인", "acknowledged": "확인됨"}[x])
    assignee = st.text_input("담당자", key="alert_assignee")
filters = {k: v for k, v in {"query": query.strip(), "status": status, "assignee": assignee.strip(),
           "patient_id": st.session_state.alert_patient_filter}.items() if v}
if period != "전체":
    today = datetime.now(KST).date()
    start = datetime.combine(today, time.min, KST) - timedelta(days=6 if period == "최근 7일" else 0)
    filters["from"] = start.isoformat()
    filters["to"] = datetime.combine(today+timedelta(days=1), time.min, KST).isoformat()
if st.session_state.alert_patient_filter:
    st.info(f"선택 환자 필터: {st.session_state.alert_patient_filter}")
    if st.button("선택 환자 필터 해제"):
        st.session_state.alert_patient_filter = None
        st.session_state.alert_cursor = None
        st.rerun()
signature = tuple(sorted(filters.items()))
if st.session_state.get("alert_signature") != signature:
    st.session_state.alert_cursor = None
st.session_state.alert_signature = signature
cursor = st.session_state.alert_cursor
key = f"alerts_{signature}_{cursor}"
page = read(st.session_state, key, lambda: gateway.list_alerts(filters, cursor), refresh)
fresh = read_feedback(key, page)
if page is None:
    st.info("목록 갱신으로 다시 조회하세요.")
    st.stop()
alert_summary(page.summary)
st.caption(f"조회 조건 전체 {page.summary.total}건 · 현재 페이지 {len(page.items)}건 · 기준 {time_label(page.as_of, True)} KST")
if page.items:
    st.dataframe(pd.DataFrame([{"환자 / 병상": f"{a.patient_id} / {a.bed or '—'}",
        "발생 당시 점수": score_label(a.risk_score), "발생 KST": time_label(a.occurred_at, True),
        "확인 KST": time_label(a.acknowledged_at, True),
        "상태": "! 미확인" if a.status == "unacknowledged" else "확인됨",
        "담당": a.assignee or "미제공", "기록": f"{len(a.records)}건", "반복": a.repeat_count}
        for a in page.items]), hide_index=True, width="stretch")
    events = {a.id: a for a in page.items}
    ids = [None, *events]
    selected = st.session_state.selected_alert_id
    # Include option IDs in the key so a removed event cannot retain a stale selection.
    picker = "history_picker_" + "_".join(events)
    event_id = st.selectbox("경보 선택", ids, index=ids.index(selected) if selected in ids else 0,
        format_func=lambda aid: "경보를 선택하세요" if aid is None else
        f"{events[aid].bed or events[aid].patient_id} · {time_label(events[aid].occurred_at, True)} · {aid}", key=picker)
    st.session_state.selected_alert_id = event_id
    if event_id:
        care_form(gateway, events[event_id], fresh)
else:
    st.session_state.selected_alert_id = None
    st.info("조건에 맞는 경보가 없습니다.")
if page.next_cursor or cursor:
    left, right = st.columns(2)
    if left.button("첫 페이지", disabled=not cursor):
        st.session_state.alert_cursor = None
        st.rerun()
    if right.button("다음 페이지", disabled=not page.next_cursor):
        st.session_state.alert_cursor = page.next_cursor
        st.rerun()
st.caption("확인은 읽음 상태입니다. 기록 저장으로 위험 단계가 바뀌거나 경보가 종료되지 않습니다.")
