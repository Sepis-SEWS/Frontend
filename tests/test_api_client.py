"""Exercise HTTP boundaries without an external Backend."""
import httpx
import pytest

from config import Settings
from domain.schemas import RecordDraft
from services.api_client import ApiGateway
from services.demo import DemoGateway
from services.gateway import ServiceError


def client(handler):
    return ApiGateway(Settings(mode="api", api_base_url="http://backend.test", token="private-token"),
                      transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("status", [401, 403, 404, 409, 422, 500, 503])
def test_status_errors_are_safe(status):
    gateway = client(lambda request: httpx.Response(status, json={"message": "SENSITIVE"}))
    with pytest.raises(ServiceError) as info:
        gateway.list_patients({})
    assert info.value.status == status
    assert "SENSITIVE" not in str(info.value)
    assert "private-token" not in str(info.value)


@pytest.mark.parametrize("body", [b"not-json", b"{}", b'{"items": []}'])
def test_invalid_responses(body):
    with pytest.raises(ServiceError):
        client(lambda request: httpx.Response(200, content=body)).list_patients({})


def test_get_validation_and_patient_identity():
    demo = DemoGateway()
    gateway = client(lambda request: httpx.Response(200, json=demo.get_patient("P-2041").model_dump(mode="json")))
    assert gateway.get_patient("P-2041").item.id == "P-2041"
    with pytest.raises(ServiceError):
        gateway.get_patient("another-patient")


def test_write_timeout_is_uncertain_and_never_retried_automatically():
    requests = []

    def timeout(request):
        requests.append(request)
        raise httpx.ReadTimeout("sensitive data", request=request)

    with pytest.raises(ServiceError) as info:
        client(timeout).save_record("alert-1", RecordDraft(assessment="평가", action="조치"), "key-1")
    assert info.value.uncertain
    assert len(requests) == 1
    assert requests[0].headers["Idempotency-Key"] == "key-1"
    assert requests[0].headers["Authorization"] == "Bearer private-token"


def test_api_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("SEWS_MODE", "api")
    monkeypatch.delenv("API_BASE_URL", raising=False)
    with pytest.raises(ValueError):
        Settings.from_env()
