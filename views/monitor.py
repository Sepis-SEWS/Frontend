"""Ward monitor with frozen ordering and explicit ID selection."""
import streamlit as st

from components.layout import heading, panel, read_feedback
from components.patient_table import patient_table
from components.risk import render_risk
from components.summary import monitor_summary
from domain.presenters import RISK_LABELS, time_label
from state import read, reconcile_order

heading("ICU 통합 모니터", "우선 확인할 환자를 빠르게 찾고, 경보와 데이터 상태를 함께 확인합니다.")


@st.fragment(run_every="30s" if st.session_state.auto_refresh else None)
def monitor() -> None:
    gateway = st.session_state.gateway
    refresh = st.button("목록 갱신", icon=":material/refresh:")
    automatic = st.session_state.auto_refresh
    global_page = read(st.session_state, "patients_global", lambda: gateway.list_patients({}), refresh or automatic)
    global_fresh = read_feedback("patients_global", global_page)
    if global_page is None:
        st.info("환자 목록을 조회하지 못했습니다. 목록 갱신으로 재시도하세요.")
        return
    if global_page.summary.scope != "global":
        st.error("서버 집계 범위가 전체가 아닙니다. API 계약을 확인하세요.")
        return
    monitor_summary(global_page.summary)
    left, right = st.columns([2, 1])
    with left:
        query = st.text_input("환자·병상 검색", placeholder="병상 또는 가명 ID", key="monitor_query")
    with right:
        risk = st.selectbox("위험도", [None, "high", "warning", "low", "unavailable"], key="monitor_risk",
                            format_func=lambda value: RISK_LABELS.get(value, "전체"))
    left, right = st.columns([2, 1])
    with left:
        assignee = st.text_input("담당자", placeholder="전체 · 이름 입력 시 필터", key="monitor_assignee")
    with right:
        st.write("")
        unacked = st.checkbox("미확인만 보기", key="monitor_unacked")
    filters = {key: value for key, value in {"query": query.strip(), "risk_level": risk,
               "assignee": assignee.strip(), "unacknowledged_only": unacked}.items() if value}
    signature = tuple(sorted(filters.items()))
    changed = signature != st.session_state.monitor_signature
    if changed or refresh:
        st.session_state.monitor_cursor = None
        st.session_state.ordered_patient_ids = []
    st.session_state.monitor_signature = signature
    cursor = st.session_state.monitor_cursor
    key = f"patients_{signature}_{cursor}"
    page = global_page if not filters and not cursor else read(
        st.session_state, key, lambda: gateway.list_patients(filters, cursor), refresh or automatic)
    fresh = global_fresh if page is global_page else read_feedback(key, page)
    if page is None:
        return
    ids = [p.id for p in page.items]
    ordered, new_count = reconcile_order(st.session_state.ordered_patient_ids, ids, reset=changed or refresh)
    st.session_state.ordered_patient_ids = ordered
    if new_count:
        st.info(f"새 환자 {new_count}명 · 목록 갱신을 누르면 우선순위에 반영합니다.")
    by_id = {p.id: p for p in page.items}
    patients = [by_id[pid] for pid in ordered]
    st.caption(f"검색 결과 {page.summary.total}명 · 현재 페이지 {len(page.items)}명 · 조회 {time_label(page.as_of, True)} KST")
    patient_id = patient_table(patients, st.session_state.compact, fresh)
    st.caption("고위험·미확인 우선 · 자동 갱신 중 목록 순서는 고정됩니다. 목록 갱신으로 새 순서를 적용하세요.")
    if page.next_cursor or cursor:
        first, next_col = st.columns(2)
        if first.button("첫 페이지", disabled=not cursor):
            st.session_state.monitor_cursor = None
            st.session_state.ordered_patient_ids = []
            st.rerun()
        if next_col.button("다음 페이지", disabled=not page.next_cursor):
            st.session_state.monitor_cursor = page.next_cursor
            st.session_state.ordered_patient_ids = []
            st.rerun()
        st.caption("우선순위와 순서 고정은 현재 서버 페이지 내 범위입니다.")
    if not patient_id:
        st.info("환자를 선택하면 최신 관측 요약과 상세 화면을 확인할 수 있습니다.")
        return
    detail_key = f"preview_{patient_id}"
    detail = read(st.session_state, detail_key, lambda: gateway.get_patient(patient_id), refresh or automatic)
    detail_fresh = read_feedback(detail_key, detail)
    if not detail:
        return
    with panel("patient_preview"):
        st.subheader(f"선택한 환자 · {detail.item.bed} / {detail.item.id}")
        columns = [st.container()] if st.session_state.compact else st.columns([1, 2])
        with columns[0]:
            render_risk(detail.item)
        with columns[-1]:
            observations = detail.item.observations[:6]
            st.write(" · ".join(f"{o.feature_name} {o.value if o.value is not None else '—'} {o.unit}" for o in observations))
            st.caption("측정 시각: " + " · ".join(f"{o.feature_name} {time_label(o.observed_at)}" for o in observations))
            st.caption(f"미리보기 조회 {time_label(detail.as_of, True)} KST · 목록과 별도 조회")
            if st.button("환자 상세 보기", type="primary", disabled=not (fresh and detail_fresh)):
                st.switch_page("views/patient_detail.py")


monitor()
