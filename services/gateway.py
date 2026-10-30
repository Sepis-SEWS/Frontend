"""One interface for HTTP and session-local synthetic data."""
from typing import Protocol

from domain.schemas import AlertEvent, CareRecord, Detail, Health, Listing, PatientSummary, RecordDraft


class ServiceError(Exception):
    """Safe user-facing error; never exposes payloads or credentials."""
    def __init__(self, message: str, *, status: int | None = None, uncertain: bool = False):
        super().__init__(message)
        self.status = status
        self.uncertain = uncertain


class Gateway(Protocol):
    def get_health(self) -> Health: ...
    def list_patients(self, filters: dict, cursor: str | None = None) -> Listing[PatientSummary]: ...
    def get_patient(self, patient_id: str) -> Detail: ...
    def list_alerts(self, filters: dict, cursor: str | None = None) -> Listing[AlertEvent]: ...
    def acknowledge_alert(self, alert_id: str) -> AlertEvent: ...
    def save_record(self, alert_id: str, draft: RecordDraft, key: str) -> CareRecord: ...
