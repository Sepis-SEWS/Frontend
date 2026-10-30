"""Risk and freshness are separate dimensions."""
from html import escape

import streamlit as st

from domain.presenters import RISK_LABELS, score_label, time_label
from domain.schemas import PatientSummary
from ui.tokens import RISK_COLORS


def render_risk(patient: PatientSummary) -> None:
    prediction = patient.prediction
    color = RISK_COLORS[prediction.risk_level]
    st.html(f'<span class="sews-badge" style="color:{color}">{escape(RISK_LABELS[prediction.risk_level])}</span>'
            f'<div class="sews-score" style="color:{color}">{score_label(prediction.risk_score)}</div>')
    st.caption("모델 점수 / 100 · 최근 24시간 관찰 기반")
    st.caption(f"관측 {time_label(patient.last_observed_at, True)} · 예측 {time_label(prediction.predicted_at, True)} KST")
    if prediction.unavailable_reason:
        st.info(prediction.unavailable_reason)
    if patient.data_delayed:
        st.warning(patient.delay_reason or "관측 데이터 지연")
    if prediction.calibration_available:
        st.write(f"보정된 발생 확률 {prediction.calibrated_probability:.1%}")
