"""Retain an immutable submission and key until its outcome is resolved."""
from collections.abc import MutableMapping
from uuid import uuid4

from domain.schemas import CareRecord, RecordDraft
from services.gateway import Gateway, ServiceError


def submit_record(gateway: Gateway, state: MutableMapping, alert_id: str, draft: RecordDraft) -> CareRecord:
    pending = state["pending_submission"]
    request = pending.get(alert_id)
    if request is not None and request["draft"] != draft:
        raise ServiceError("이전 제출의 결과를 먼저 확인하거나 같은 내용으로 재시도하세요.")
    if request is None:
        request = {"key": str(uuid4()), "draft": draft.model_copy(deep=True), "uncertain": False}
        pending[alert_id] = request
    try:
        record = gateway.save_record(alert_id, request["draft"], request["key"])
    except ServiceError as exc:
        request["uncertain"] = exc.uncertain
        if not exc.uncertain and exc.status in {401, 403, 404, 409, 422}:
            pending.pop(alert_id, None)
        raise
    pending.pop(alert_id, None)
    state["record_drafts"].pop(alert_id, None)
    state["form_generation"][alert_id] = state["form_generation"].get(alert_id, 0) + 1
    return record
