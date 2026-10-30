"""Explicit acknowledgement and record submission, outside refresh fragments."""
import streamlit as st
from pydantic import ValidationError

from domain.presenters import score_label, time_label
from domain.schemas import AlertEvent, RecordDraft
from services.alerts import submit_record
from services.gateway import Gateway, ServiceError
from state import invalidate
from components.layout import panel


def current_event(gateway: Gateway, event: AlertEvent) -> AlertEvent:
    """Revalidate the selected event's identity and status immediately before writes."""
    cursor, seen = None, set()
    while True:
        page = gateway.list_alerts({"patient_id": event.patient_id}, cursor)
        found = next((a for a in page.items if a.id == event.id), None)
        if found is not None:
            if found.patient_id != event.patient_id:
                raise ServiceError("경보와 환자 식별자가 다릅니다.")
            return found
        cursor = page.next_cursor
        if cursor is None:
            raise ServiceError("선택 경보가 더 이상 조회되지 않습니다.", status=404)
        if cursor in seen or len(seen) >= 100:
            raise ServiceError("경보 목록을 완전히 확인하지 못했습니다.")
        seen.add(cursor)


def _save(gateway: Gateway, event: AlertEvent, draft: RecordDraft) -> None:
    try:
        latest = current_event(gateway, event)
        if latest.status != "acknowledged":
            raise ServiceError("먼저 경보를 확인하세요.", status=409)
        submit_record(gateway, st.session_state, event.id, draft)
    except ServiceError as exc:
        st.error(str(exc))
        if exc.uncertain:
            st.warning("저장 결과를 확인하지 못했습니다. 같은 제출 키와 본문으로 재시도하세요.")
        return
    invalidate(st.session_state)
    st.session_state.notice = "데모 기록을 세션에 저장했습니다." if st.session_state.settings.mode == "demo" else "서버에 기록을 저장했습니다."
    st.rerun()


def care_form(gateway: Gateway, event: AlertEvent, fresh: bool = True) -> None:
    with panel("care_form"):
        st.subheader("선택 경보 · 확인 및 평가/조치")
        st.write(f"{event.bed or event.patient_id} · {event.id}")
        st.caption(f"발생 {time_label(event.occurred_at, True)} KST · 발생 당시 점수 {score_label(event.risk_score)}")
        if event.status == "unacknowledged":
            st.info("미확인 · 확인은 읽음 상태이며 위험 해소나 치료 완료가 아닙니다.")
            if st.button("경보 확인", type="primary", key=f"ack_{event.id}", disabled=not fresh):
                try:
                    current_event(gateway, event)
                    gateway.acknowledge_alert(event.id)
                except ServiceError as exc:
                    st.error(str(exc))
                else:
                    invalidate(st.session_state)
                    st.rerun()
            return
        st.caption(f"확인자 {event.acknowledged_by} · {time_label(event.acknowledged_at, True)} KST")
        for record in event.records:
            with st.expander(f"{time_label(record.saved_at, True)} · {record.author}"):
                st.text(f"평가: {record.assessment}\n조치: {record.action}")
        pending = st.session_state.pending_submission.get(event.id)
        if pending:
            st.warning("처리 중인 제출이 있습니다. 본문을 보존한 상태로 같은 요청을 재시도할 수 있습니다.")
            st.text(f"평가: {pending['draft'].assessment}\n조치: {pending['draft'].action}")
            if st.button("같은 내용으로 저장 재시도", key=f"retry_{event.id}", disabled=not fresh):
                _save(gateway, event, pending["draft"])
            return
        generation = st.session_state.form_generation.get(event.id, 0)
        draft = st.session_state.record_drafts.get(event.id, {})
        with st.form(f"care_{event.id}_{generation}"):
            assessment = st.text_area("환자 평가", value=draft.get("assessment", ""), max_chars=2000)
            action = st.text_area("조치 및 계획", value=draft.get("action", ""), max_chars=2000)
            st.caption("기록 저장은 경보 종료를 의미하지 않습니다. 미제출 입력은 페이지 이동 시 사라질 수 있습니다.")
            submitted = st.form_submit_button("평가·조치 저장", type="primary", disabled=not fresh)
        if submitted:
            st.session_state.record_drafts[event.id] = {"assessment": assessment, "action": action}
            try:
                validated = RecordDraft(assessment=assessment, action=action)
            except ValidationError:
                st.error("평가와 조치를 각각 공백을 제외한 1–2000자로 입력하세요.")
                return
            _save(gateway, event, validated)
