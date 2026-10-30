"""Figma priority cards, with values supplied only by response summaries."""
from html import escape

import streamlit as st

from domain.schemas import Summary
from ui.tokens import MUTED, RED, TEXT


def cards(items: list[tuple[str, str, str, str]]) -> None:
    for col, (label, value, note, color) in zip(st.columns(len(items)), items):
        with col:
            st.html(f'<div class="sews-card"><div class="sews-card-label">{escape(label)}</div>'
                    f'<div class="sews-card-value" style="color:{color}">{escape(value)}</div>'
                    f'<div class="sews-card-note">{escape(note)}</div></div>')


def monitor_summary(summary: Summary) -> None:
    cards([("전체 환자", str(summary.total), "ICU-A · 관찰 중", TEXT),
           ("고위험", str(summary.high), "모델 위험 단계 기준", RED),
           ("주의", str(summary.warning), "담당자 평가 필요", "#B54708"),
           ("미확인 경보", str(summary.unacknowledged_alert_count), "경보 확인 필요", RED)])
    st.write("")
    if summary.unacknowledged_high_count:
        st.warning(f"! 미확인 고위험 경보 {summary.unacknowledged_high_count}건 · 환자를 선택해 근거를 확인하세요.")
    st.caption(f"예측 불가 {summary.unavailable_count}명 · 예측 불가는 낮음과 별도 상태입니다.")


def alert_summary(summary: Summary) -> None:
    cards([("미확인", str(summary.unacknowledged_alert_count), "조회 조건 전체 경보", RED),
           ("확인됨", str(summary.acknowledged_count), "확인은 읽음 상태", TEXT),
           ("기록 있음", str(summary.recorded_count), "평가·조치 기록이 있는 경보", MUTED)])
    st.write("")
