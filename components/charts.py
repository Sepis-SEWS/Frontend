"""Data-driven charts; never render static Figma sample curves as patient data."""
from datetime import timedelta

import plotly.graph_objects as go
import streamlit as st

from domain.presenters import KST
from domain.schemas import PatientDetail
from ui.tokens import BLUE, BLUE_SOFT, BORDER, MUTED, PANEL, RED, TEXT
from components.layout import panel


def base_figure(height: int = 260) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(height=height, margin=dict(l=10, r=16, t=15, b=25),
                      paper_bgcolor=PANEL, plot_bgcolor=PANEL,
                      font=dict(family="sans-serif", size=12, color=TEXT),
                      xaxis=dict(showgrid=False), yaxis=dict(gridcolor=BORDER), showlegend=False)
    return fig


def risk_chart(patient: PatientDetail) -> None:
    with panel("risk_chart"):
        st.subheader("모델 위험 점수 추세")
        st.caption("실선: 과거 예측 이력 · 파란 영역: 현재 예측의 향후 6시간 평가 구간")
        points = sorted([p for p in patient.series if p.predicted_at is not None], key=lambda p: p.predicted_at)
        current = patient.prediction.predicted_at
        if current:
            points = [p for p in points if current-timedelta(hours=24) <= p.predicted_at <= current]
        if not any(p.risk_score is not None for p in points):
            st.info("표시할 예측 이력이 없습니다.")
            return
        fig = base_figure()
        fig.add_trace(go.Scatter(x=[p.predicted_at.astimezone(KST) for p in points],
            y=[None if p.risk_score is None else p.risk_score*100 for p in points],
            connectgaps=False, mode="lines", line=dict(color=BLUE, width=2),
            hovertemplate="%{x|%m.%d %H:%M}<br>모델 점수 %{y:.0f} / 100<extra></extra>"))
        if current:
            start, end = current.astimezone(KST), (current+timedelta(hours=6)).astimezone(KST)
            fig.add_vrect(x0=start, x1=end, fillcolor=BLUE_SOFT, opacity=.8, line_width=0, layer="below")
            fig.add_vline(x=start, line_dash="dot", line_color=MUTED)
            fig.update_xaxes(range=[start-timedelta(hours=24), end])
        fig.update_yaxes(range=[0, 100], title_text="모델 점수 / 100")
        st.plotly_chart(fig, width="stretch", key=f"risk_{patient.id}")
        st.caption("미래 점수 곡선은 표시하지 않습니다. 결측 구간은 연결하지 않습니다.")


def observation_chart(patient: PatientDetail, feature: str) -> None:
    points = sorted(patient.series, key=lambda p: p.observed_at)
    fig = base_figure(180)
    fig.add_trace(go.Scatter(x=[p.observed_at.astimezone(KST) for p in points],
                            y=[getattr(p, feature) for p in points], connectgaps=False,
                            mode="lines+markers", line=dict(color=MUTED, width=2), marker=dict(size=3)))
    st.plotly_chart(fig, width="stretch", key=f"observations_{patient.id}")


def contributions(patient: PatientDetail) -> None:
    explanation = patient.explanation
    st.subheader("예측에 기여한 주요 특징")
    if not explanation.available:
        st.info(explanation.unavailable_reason or "설명 미제공")
        return
    if (not explanation.prediction_id or explanation.prediction_id != patient.prediction.prediction_id
            or explanation.model_version != patient.prediction.model_version):
        st.warning("현재 예측과 설명의 식별자·모델 버전을 확인할 수 없어 표시하지 않습니다.")
        return
    if not explanation.features:
        st.info("설명 특징이 없습니다.")
        return
    st.caption("합성 예시 · 실제 SHAP가 아닙니다." if explanation.method == "synthetic-demo"
               else f"설명 방식: {explanation.method or '미제공'}")
    features = sorted(explanation.features, key=lambda f: abs(f.contribution))[-8:]
    fig = base_figure(280)
    fig.add_trace(go.Bar(y=[f.name for f in features], x=[f.contribution for f in features],
        orientation="h", marker_color=[RED if f.contribution > 0 else BLUE for f in features],
        text=[f"{f.contribution:+.3f}" for f in features], textposition="auto"))
    fig.update_xaxes(title_text=explanation.output_scale or "출력 척도 미제공")
    st.plotly_chart(fig, width="stretch", key=f"explanation_{patient.id}")
    st.caption("기여도는 원인·진단 또는 확률 변화량을 의미하지 않습니다.")
