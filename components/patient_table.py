"""Stable ID selection despite sorting, filtering and refreshed rows."""
import hashlib

import pandas as pd
import streamlit as st

from domain.presenters import RISK_LABELS, TRENDS, score_label, time_label
from domain.schemas import PatientSummary


def patient_table(patients: list[PatientSummary], compact: bool, fresh: bool) -> str | None:
    ids = [p.id for p in patients]
    if st.session_state.selected_patient_id not in ids:
        st.session_state.selected_patient_id = None
    if not patients:
        st.info("조건에 맞는 환자가 없습니다.")
        return None
    rows = [{"병상 / ID": f"{p.bed} / {p.id}", "위험 상태": RISK_LABELS[p.prediction.risk_level],
             "모델 점수": score_label(p.prediction.risk_score), "추세": TRENDS[p.trend],
             "관측 / 예측": f"{time_label(p.last_observed_at)} / {time_label(p.prediction.predicted_at)}",
             "담당": p.assignee, "경보": ("미제공" if p.unacknowledged_alert_count is None else
                 f"! 미확인 {p.unacknowledged_alert_count}건" if p.unacknowledged_alert_count else "—"),
             "데이터": p.delay_reason if p.data_delayed else "—"} for p in patients]
    frame = pd.DataFrame(rows)
    if compact:
        frame = frame[["병상 / ID", "위험 상태", "모델 점수", "관측 / 예측", "경보"]]
    digest = hashlib.sha256("|".join(ids).encode()).hexdigest()[:12]
    table_key, picker_key = f"patient_table_{digest}", f"patient_picker_{digest}"
    event = st.dataframe(frame, hide_index=True, width="stretch", height=min(500, 40+len(rows)*44),
                         on_select="rerun", selection_mode="single-row", key=table_key,
                         row_height=44)
    selection = tuple(event.selection.rows)
    marker = (table_key, selection)
    if st.session_state.get("processed_patient_selection") != marker:
        st.session_state.processed_patient_selection = marker
        if selection and fresh:
            st.session_state.selected_patient_id = ids[selection[0]]
            st.session_state[picker_key] = ids[selection[0]]
    options = [None, *ids]
    if picker_key not in st.session_state or st.session_state[picker_key] not in options:
        st.session_state[picker_key] = st.session_state.selected_patient_id
    labels = {p.id: f"{p.bed} / {p.id}" for p in patients}
    choice = st.selectbox("환자 선택", options, key=picker_key, disabled=not fresh,
                          format_func=lambda value: labels.get(value, "환자를 선택하세요"))
    if fresh:
        st.session_state.selected_patient_id = choice
    return st.session_state.selected_patient_id
