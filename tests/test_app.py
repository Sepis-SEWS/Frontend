"""Streamlit workflows, including reruns and blank/failed form submissions."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SEWS_MODE", "demo")
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()


def element(elements, label):
    return next(e for e in elements if e.label == label)


def test_monitor_filters_clear_invisible_patient(app):
    assert not app.exception
    element(app.selectbox, "환자 선택").select("P-2041").run()
    assert app.session_state["selected_patient_id"] == "P-2041"
    element(app.text_input, "환자·병상 검색").input("no-such-patient").run()
    assert app.session_state["selected_patient_id"] is None
    assert not app.exception


def test_patient_ack_record_and_reruns_do_not_duplicate(app):
    element(app.selectbox, "환자 선택").select("P-2041").run()
    element(app.button, "환자 상세 보기").click().run()
    assert not app.exception
    element(app.selectbox, "경보 선택").select("demo-alert-0").run()
    gateway = app.session_state["gateway"]
    assert gateway.alerts["demo-alert-0"].status == "unacknowledged"
    element(app.button, "경보 확인").click().run()
    assert gateway.alerts["demo-alert-0"].status == "acknowledged"
    element(app.button, "평가·조치 저장").click().run()
    assert app.error
    assert not gateway.alerts["demo-alert-0"].records
    element(app.text_area, "환자 평가").input("데모 평가")
    element(app.text_area, "조치 및 계획").input("데모 조치")
    element(app.button, "평가·조치 저장").click().run()
    assert not app.exception
    assert len(gateway.alerts["demo-alert-0"].records) == 1
    assert not element(app.text_area, "환자 평가").value
    app.run()
    assert len(gateway.alerts["demo-alert-0"].records) == 1
    element(app.button, "환자 경보 이력 보기").click().run()
    assert not app.exception
    assert app.session_state["alert_patient_filter"] == "P-2041"


def test_no_selection_and_compact_mode(app):
    app.switch_page("views/patient_detail.py").run()
    assert not app.exception
    assert any("먼저 선택" in item.value for item in app.info)
    app.switch_page("views/monitor.py").run()
    element(app.toggle, "간결 보기").set_value(True).run()
    element(app.selectbox, "환자 선택").select("P-2041").run()
    element(app.button, "환자 상세 보기").click().run()
    assert not app.exception


def test_two_apps_do_not_share_demo_acknowledgements(app):
    other = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.session_state["gateway"].acknowledge_alert("demo-alert-0")
    assert other.session_state["gateway"].alerts["demo-alert-0"].status == "unacknowledged"


def test_filters_survive_page_navigation(app):
    element(app.text_input, "환자·병상 검색").input("ICU-03").run()
    app.switch_page("views/alerts.py").run()
    app.switch_page("views/monitor.py").run()
    assert element(app.text_input, "환자·병상 검색").value == "ICU-03"


def test_form_retains_failed_submission_and_pending_body(app):
    from services.gateway import ServiceError

    element(app.selectbox, "환자 선택").select("P-2041").run()
    element(app.button, "환자 상세 보기").click().run()
    element(app.selectbox, "경보 선택").select("demo-alert-0").run()
    element(app.button, "경보 확인").click().run()
    gateway = app.session_state["gateway"]
    save = gateway.save_record

    def timeout(*args):
        raise ServiceError("연결 시간 초과", uncertain=True)

    gateway.save_record = timeout
    element(app.text_area, "환자 평가").input("보존할 평가")
    element(app.text_area, "조치 및 계획").input("보존할 조치")
    element(app.button, "평가·조치 저장").click().run()
    assert app.error
    assert app.session_state["record_drafts"]["demo-alert-0"]["assessment"] == "보존할 평가"
    assert app.session_state["pending_submission"]["demo-alert-0"]["draft"].action == "보존할 조치"
    gateway.save_record = save
    app.run()
    element(app.button, "같은 내용으로 저장 재시도").click().run()
    assert len(gateway.alerts["demo-alert-0"].records) == 1
    assert not app.exception
