"""Check response aggregates and IDs rather than inventing absent values."""
import httpx
import pytest

from config import Settings
from services.api_client import ApiGateway
from services.demo import DemoGateway
from services.gateway import ServiceError


def gateway(payload):
    return ApiGateway(Settings(mode="api", api_base_url="http://backend.test"),
                      transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))


def test_patient_listing_accepts_explicit_aggregates_and_rejects_missing_counts():
    payload = DemoGateway().list_patients({}).model_dump(mode="json")
    assert gateway(payload).list_patients({}).summary.total == 24
    del payload["summary"]["unavailable_count"]
    with pytest.raises(ServiceError):
        gateway(payload).list_patients({})


def test_duplicate_patient_ids_are_not_selectable():
    payload = DemoGateway().list_patients({}).model_dump(mode="json")
    payload["items"].append(payload["items"][0])
    with pytest.raises(ServiceError):
        gateway(payload).list_patients({})


def test_alerts_must_belong_to_requested_patient():
    payload = DemoGateway().list_alerts({}).model_dump(mode="json")
    with pytest.raises(ServiceError):
        gateway(payload).list_alerts({"patient_id": "different-patient"})
