"""Writes, stable ordering and session isolation."""
import pytest

from domain.schemas import RecordDraft
from services.alerts import submit_record
from services.demo import DemoGateway
from services.gateway import ServiceError
from state import initialize, read, reconcile_order


def test_acknowledgement_is_idempotent_and_does_not_lower_risk():
    gateway = DemoGateway()
    score = gateway.get_patient("P-2041").item.prediction.risk_score
    first = gateway.acknowledge_alert("demo-alert-0")
    second = gateway.acknowledge_alert("demo-alert-0")
    assert first == second
    assert gateway.get_patient("P-2041").item.prediction.risk_score == score


def test_record_requires_ack_and_key_cannot_change_body():
    gateway = DemoGateway()
    draft = RecordDraft(assessment="평가", action="조치")
    with pytest.raises(ServiceError):
        gateway.save_record("demo-alert-0", draft, "same")
    gateway.acknowledge_alert("demo-alert-0")
    first = gateway.save_record("demo-alert-0", draft, "same")
    assert gateway.save_record("demo-alert-0", draft, "same") == first
    with pytest.raises(ServiceError):
        gateway.save_record("demo-alert-0", RecordDraft(assessment="다른 평가", action="조치"), "same")
    assert len(gateway.alerts["demo-alert-0"].records) == 1


def test_timeout_after_commit_reuses_immutable_request():
    gateway, state = DemoGateway(), {}
    initialize(state)
    gateway.acknowledge_alert("demo-alert-0")
    original = gateway.save_record
    calls = []

    def commit_then_timeout(alert_id, draft, key):
        result = original(alert_id, draft, key)
        calls.append(key)
        if len(calls) == 1:
            raise ServiceError("timeout", uncertain=True)
        return result

    gateway.save_record = commit_then_timeout
    draft = RecordDraft(assessment="평가", action="조치")
    with pytest.raises(ServiceError):
        submit_record(gateway, state, "demo-alert-0", draft)
    with pytest.raises(ServiceError):
        submit_record(gateway, state, "demo-alert-0", RecordDraft(assessment="수정", action="조치"))
    submit_record(gateway, state, "demo-alert-0", draft)
    assert calls[0] == calls[1]
    assert len(gateway.alerts["demo-alert-0"].records) == 1
    assert not state["pending_submission"]


def test_sessions_and_returned_objects_are_isolated():
    first, second = DemoGateway(), DemoGateway()
    first.acknowledge_alert("demo-alert-0")
    assert second.alerts["demo-alert-0"].status == "unacknowledged"
    detail = first.get_patient("P-2041")
    detail.item.assignee = "changed"
    assert first.get_patient("P-2041").item.assignee != "changed"


def test_frozen_order_removes_departed_and_defers_new():
    assert reconcile_order(["a", "b"], ["b", "c", "a"], False) == (["a", "b"], 1)
    assert reconcile_order(["a", "b"], ["b", "c"], False) == (["b"], 1)
    assert reconcile_order(["a", "b"], ["b", "c"], True) == (["b", "c"], 0)


def test_read_failures_are_marked_instead_of_synthetic_fallback():
    state = {}
    initialize(state)
    read(state, "x", lambda: "previous")

    def failing():
        raise ServiceError("offline")

    assert read(state, "x", failing, True) == "previous"
    assert state["read_errors"]["x"] == "offline"


@pytest.mark.parametrize("status", [401, 403, 404])
def test_access_denied_or_departed_patient_removes_previous_data(status):
    state = {}
    initialize(state)
    read(state, "patient", lambda: "previous")

    def failing():
        raise ServiceError("inaccessible", status=status)

    assert read(state, "patient", failing, True) is None
    assert "patient" not in state["read_results"]
