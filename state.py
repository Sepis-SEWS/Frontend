"""Session-only UI state; no globally cached patient data or credentials."""
from collections.abc import Callable, MutableMapping


def initialize(state: MutableMapping) -> None:
    for key, value in {"selected_patient_id": None, "selected_alert_id": None,
                       "record_drafts": {}, "pending_submission": {}, "form_generation": {},
                       "read_results": {}, "read_errors": {}, "ordered_patient_ids": [],
                       "monitor_signature": None, "monitor_cursor": None,
                       "alert_cursor": None, "alert_patient_filter": None}.items():
        if key not in state:
            state[key] = value
    # Detach these keys from Streamlit's per-page widget cleanup on every run.
    # Their values are UI filters, never credentials or persistent patient records.
    for key in ("monitor_query", "monitor_risk", "monitor_assignee", "monitor_unacked",
                "alert_period", "alert_query", "alert_status", "alert_assignee"):
        if key in state:
            state[key] = state[key]


def read(state: MutableMapping, key: str, loader: Callable, refresh: bool = False):
    """Cache successful reads per session until explicit invalidation."""
    from services.gateway import ServiceError
    if refresh or key not in state["read_results"]:
        try:
            state["read_results"][key] = loader()
            state["read_errors"].pop(key, None)
        except ServiceError as exc:
            state["read_errors"][key] = str(exc)
            if exc.status in {401, 403, 404}:
                state["read_results"].pop(key, None)
    return state["read_results"].get(key)


def invalidate(state: MutableMapping) -> None:
    state["read_results"].clear()
    state["read_errors"].clear()


def reconcile_order(previous: list[str], current: list[str], reset: bool) -> tuple[list[str], int]:
    """Keep existing positions and defer new patients until explicit refresh."""
    if reset or not previous:
        return list(current), 0
    available = set(current)
    return [pid for pid in previous if pid in available], len(available - set(previous))
