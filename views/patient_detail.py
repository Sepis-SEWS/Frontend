"""Selected patient detail: observations, predictions, explanations and actions."""
import pandas as pd
import streamlit as st

from components.care_form import care_form
from components.charts import contributions, observation_chart, risk_chart
from components.layout import heading, panel, read_feedback
from components.risk import render_risk
from domain.presenters import time_label
from state import read

gateway = st.session_state.gateway
patient_id = st.session_state.selected_patient_id
if st.button("← 통합 모니터"):
    st.switch_page("views/monitor.py")
if not patient_id:
    st.info("통합 모니터에서 환자를 먼저 선택하세요.")
    st.stop()
refresh = st.button("환자 정보 갱신", icon=":material/refresh:")
key = f"patient_{patient_id}"
detail = read(st.session_state, key, lambda: gateway.get_patient(patient_id), refresh)
fresh = read_feedback(key, detail)
if detail is None:
    st.stop()
if st.session_state.read_errors.get(key) and not fresh:
    st.warning("환자 접근 가능 여부를 다시 확인할 때까지 상세 액션을 사용할 수 없습니다.")
patient = detail.item
heading(f"{patient.bed} / {patient.id}", f"환자 식별 재확인 · {patient.icu_id} · 담당 {patient.assignee}")
with panel("patient_risk"):
    left, right = st.columns([1, 1])
    with left:
        render_risk(patient)
    with right:
        st.caption(f"모델 {patient.prediction.model_version}")
        st.caption(f"임계값 버전 {patient.prediction.threshold_version}")
        st.caption(f"조회 기준 {time_label(detail.as_of, True)} KST")
        st.caption("경보 확인 = 읽음 · 평가/조치 기록은 아래 경보를 선택해 작성합니다.")
risk_chart(patient)
containers = [st.container(), st.container()] if st.session_state.compact else st.columns(2)
with containers[0]:
    with panel("observations"):
        st.subheader("생체·검사 추세")
        st.caption("측정 시각과 결측을 함께 확인합니다.")
        labels = {"Resp": "RR", "O2Sat": "SpO₂", "Temp": "체온"}
        st.dataframe(pd.DataFrame([{"지표": labels.get(o.feature_name, o.feature_name),
            "값": "— 미측정" if o.value is None else f"{o.value:g}", "단위": o.unit,
            "측정 시각 KST": time_label(o.observed_at, True)} for o in patient.observations]),
            hide_index=True, width="stretch")
        st.caption("RR=Resp, SpO₂=O2Sat · 화면 라벨 매핑")
        feature = st.selectbox("추세 지표", ["map", "hr", "lactate"], format_func=lambda f: f.upper())
        observation_chart(patient, feature)
        st.caption("SOFA " + (str(patient.sofa.total) if patient.sofa.available else
                               f"계산 불가 · {patient.sofa.unavailable_reason or '원천정보 미제공'}"))
with containers[1]:
    with panel("contributions"):
        contributions(patient)
st.subheader("경보 활동")
alert_key = f"patient_alerts_{patient_id}"
alerts = read(st.session_state, alert_key, lambda: gateway.list_alerts({"patient_id": patient_id}), refresh)
alerts_fresh = read_feedback(alert_key, alerts)
if alerts:
    if alerts.next_cursor:
        st.caption("현재 페이지 경보만 표시합니다. 전체 조회는 경보 이력에서 확인하세요.")
    events = {a.id: a for a in alerts.items if a.patient_id == patient_id}
    options = [None, *events]
    selected = st.session_state.selected_alert_id
    event_id = st.selectbox("경보 선택", options, index=options.index(selected) if selected in options else 0,
        format_func=lambda aid: "경보를 선택하세요" if aid is None else
        f"{time_label(events[aid].occurred_at, True)} · {aid} · {'미확인' if events[aid].status == 'unacknowledged' else '확인됨'}",
        key=f"detail_alert_picker_{patient_id}")
    st.session_state.selected_alert_id = event_id
    if event_id:
        care_form(gateway, events[event_id], fresh and alerts_fresh)
    elif not events:
        st.info("이 환자의 경보가 없습니다.")
if st.button("환자 경보 이력 보기"):
    st.session_state.alert_patient_filter = patient_id
    st.session_state.alert_cursor = None
    st.switch_page("views/alerts.py")
