"""HTTP adapter: no retry of writes, no silent synthetic fallback."""
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from config import Settings
from domain.schemas import AlertEvent, CareRecord, Detail, Health, Listing, PatientSummary, RecordDraft
from services.gateway import ServiceError


class ApiGateway:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def _request(self, method: str, path: str, schema: type, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.settings.token:
            headers["Authorization"] = f"Bearer {self.settings.token}"
        try:
            with httpx.Client(base_url=self.settings.api_base_url + "/", transport=self.transport,
                              timeout=httpx.Timeout(self.settings.read_timeout,
                                                    connect=self.settings.connect_timeout)) as client:
                response = client.request(method, path, headers=headers, **kwargs)
                response.raise_for_status()
                return schema.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            messages = {401: "인증이 필요합니다.", 403: "접근 권한이 없습니다.",
                        404: "대상을 찾을 수 없습니다. 목록을 다시 조회하세요.",
                        409: "상태 또는 제출 키가 충돌했습니다. 새로 조회하세요.",
                        422: "서버가 입력을 거부했습니다. 계약을 확인하세요."}
            raise ServiceError(messages.get(status, "서버 요청에 실패했습니다."), status=status,
                               uncertain=method == "POST" and status >= 500) from None
        except (httpx.RequestError, ValueError, ValidationError):
            raise ServiceError("연결·응답 형식을 확인할 수 없습니다. 다시 조회하세요.",
                               uncertain=method == "POST") from None

    def get_health(self) -> Health:
        return self._request("GET", "health", Health)

    def list_patients(self, filters: dict, cursor: str | None = None) -> Listing[PatientSummary]:
        result = self._request("GET", "patients", Listing[PatientSummary],
                               params={**filters, **({"cursor": cursor} if cursor else {}), "limit": 100})
        required = {"high", "warning", "unavailable_count", "unacknowledged_alert_count", "unacknowledged_high_count"}
        if not required.issubset(result.summary.model_fields_set):
            raise ServiceError("환자 전체 집계 필드가 누락되었습니다. API 계약을 확인하세요.")
        if len({p.id for p in result.items}) != len(result.items):
            raise ServiceError("환자 목록에 중복 식별자가 있습니다.")
        return result

    def get_patient(self, patient_id: str) -> Detail:
        result = self._request("GET", f"patients/{quote(patient_id, safe='')}", Detail)
        if result.item.id != patient_id:
            raise ServiceError("응답 환자 식별자가 요청과 다릅니다.")
        return result

    def list_alerts(self, filters: dict, cursor: str | None = None) -> Listing[AlertEvent]:
        result = self._request("GET", "alerts", Listing[AlertEvent],
                               params={**filters, **({"cursor": cursor} if cursor else {}), "limit": 100})
        if not {"unacknowledged_alert_count", "acknowledged_count", "recorded_count"}.issubset(
                result.summary.model_fields_set):
            raise ServiceError("경보 전체 집계 필드가 누락되었습니다. API 계약을 확인하세요.")
        if filters.get("patient_id") and any(a.patient_id != filters["patient_id"] for a in result.items):
            raise ServiceError("선택 환자와 경보 응답이 일치하지 않습니다.")
        if len({a.id for a in result.items}) != len(result.items):
            raise ServiceError("경보 목록에 중복 식별자가 있습니다.")
        return result

    def acknowledge_alert(self, alert_id: str) -> AlertEvent:
        event = self._request("POST", f"alerts/{quote(alert_id, safe='')}/acknowledgement", AlertEvent)
        if event.id != alert_id or event.status != "acknowledged":
            raise ServiceError("경보 확인 응답이 일치하지 않습니다.", uncertain=True)
        return event

    def save_record(self, alert_id: str, draft: RecordDraft, key: str) -> CareRecord:
        record = self._request("POST", f"alerts/{quote(alert_id, safe='')}/records", CareRecord,
                               json=draft.model_dump(), headers={"Idempotency-Key": key})
        if record.alert_id != alert_id or record.assessment != draft.assessment or record.action != draft.action:
            raise ServiceError("저장 응답이 제출 내용과 다릅니다.", uncertain=True)
        return record
