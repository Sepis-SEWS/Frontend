"""Contract invariants that prevent misleading clinical displays."""
import pytest
from pydantic import ValidationError

from domain.presenters import score_label
from domain.schemas import Prediction, RecordDraft
from services.demo import DemoGateway


def test_zero_is_not_missing_and_null_is_not_low():
    data = DemoGateway().get_patient("P-2041").item.prediction.model_dump()
    assert score_label(0) == "0 / 100"
    assert score_label(None) == "—"
    for change in [{"risk_score": None}, {"risk_score": 68}, {"risk_score": float("nan")},
                   {"predicted_at": "2026-10-30T14:30:00"}, {"calibration_available": True}]:
        with pytest.raises(ValidationError):
            Prediction.model_validate({**data, **change})


def test_trimmed_record_and_blank_rejection():
    assert RecordDraft(assessment=" 評価 ", action=" action ").action == "action"
    with pytest.raises(ValidationError):
        RecordDraft(assessment=" \n ", action="action")


def test_demo_returns_valid_models_and_missing_data():
    gateway = DemoGateway()
    page = gateway.list_patients({})
    assert page.summary.total == 24
    assert page.summary.high == 3
    assert page.summary.unacknowledged_alert_count == 2
    unavailable = gateway.list_patients({"risk_level": "unavailable"})
    assert len(unavailable.items) == 1
    assert unavailable.items[0].prediction.risk_score is None
    for p in page.items:
        detail = gateway.get_patient(p.id)
        assert not detail.item.sofa.available
        assert any(point.map is None for point in detail.item.series)
