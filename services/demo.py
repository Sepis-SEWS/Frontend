"""Synthetic fixtures and writes owned by one Streamlit session, never global."""
import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from domain.schemas import (
    AlertEvent, CareRecord, Detail, Explanation, Health, Listing, Observation,
    PatientDetail, PatientSummary, Prediction, RecordDraft, SOFA, Summary, TimePoint,
)
from services.gateway import ServiceError


class DemoGateway:
    """Each instance is an independent synthetic ward with idempotent writes."""
    def __init__(self):
        self.anchor = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.patients: dict[str, PatientDetail] = {}
        self.alerts: dict[str, AlertEvent] = {}
        self.submissions: dict[str, tuple[str, RecordDraft, CareRecord]] = {}
        self.revision = 0
        beds = [3, 11, 7, 12, 18] + [n for n in range(1, 25) if n not in {3, 11, 7, 12, 18}]
        for index, bed in enumerate(beds):
            patient_id = f"P-{2041 + index * 13}"
            level = ["high", "high", "warning", "low", "unavailable", "high",
                     "warning", "warning", "warning", "warning"][index] if index < 10 else "low"
            score = {"high": .68 - index * .005, "warning": .34 + index * .01,
                     "low": .08 + index * .003, "unavailable": None}[level]
            delayed = level == "unavailable"
            observed = self.anchor - timedelta(minutes=28 if delayed else 2)
            prediction = Prediction(risk_score=score, risk_level=level,
                                    predicted_at=None if delayed else self.anchor,
                                    model_version="synthetic-demo-v1", threshold_version="demo-only",
                                    prediction_id=f"demo-pred-{index}",
                                    unavailable_reason="합성 시나리오: 수집 지연" if delayed else None)
            observations = [Observation(feature_name=name, value=value, unit=unit,
                                         observed_at=observed - timedelta(minutes=78 if name == "Lactate" else 0)
                                         if value is not None else None)
                            for name, value, unit in [("HR", 112-index, "bpm"), ("MAP", 62+index, "mmHg"),
                                ("Resp", 25-index % 8, "/min"), ("Temp", round(38.4-index*.05, 1), "°C"),
                                ("O2Sat", 95+index % 4, "%"), ("Lactate", 2.8, "mmol/L"),
                                ("WBC", None, "10³/µL")]]
            series = []
            for hour in range(25):
                when = self.anchor - timedelta(hours=24-hour)
                gap = hour in {8, 9}
                series.append(TimePoint(observed_at=when, predicted_at=when,
                    risk_score=None if score is None or gap else max(0, round(score*(.25+.75*hour/24), 3)),
                    hr=None if gap else 90+index+math.sin(hour)*4,
                    map=None if gap else 78-index*.2-hour*.55,
                    lactate=None if hour % 4 else 1.2+hour*.06))
            explanation = Explanation(available=not delayed, method="synthetic-demo",
                model_version=prediction.model_version, prediction_id=prediction.prediction_id,
                output_scale="합성 기여도 (모델 출력 아님)",
                features=[] if delayed else [dict(name=n, contribution=v) for n, v in
                    [("MAP 하락", .18), ("Lactate 상승", .14), ("HR 상승", .09), ("SpO₂ 유지", -.04)]],
                unavailable_reason="합성 시나리오: 예측 미제공" if delayed else None)
            self.patients[patient_id] = PatientDetail(id=patient_id, bed=f"ICU-{bed:02}",
                assignee=["김○○", "박○○", "이○○"][index % 3], last_observed_at=observed,
                prediction=prediction, data_delayed=delayed,
                delay_reason="합성 시나리오: 수집 지연 28분" if delayed else None,
                trend="rising" if level in {"high", "warning"} else "stable",
                observations=observations, series=series, explanation=explanation,
                sofa=SOFA(unavailable_reason="GCS·승압제·소변량 등 원천정보 미제공"))
            if index in {0, 1, 2, 5}:
                alert_id = f"demo-alert-{index}"
                acknowledged = index in {2, 5}
                self.alerts[alert_id] = AlertEvent(id=alert_id, patient_id=patient_id,
                    bed=f"ICU-{bed:02}", assignee=self.patients[patient_id].assignee,
                    risk_score=score, risk_level=level, model_version=prediction.model_version,
                    threshold_version="demo-only", occurred_at=self.anchor-timedelta(minutes=12+index*4),
                    status="acknowledged" if acknowledged else "unacknowledged",
                    acknowledged_at=self.anchor-timedelta(minutes=3) if acknowledged else None,
                    acknowledged_by="데모 사용자" if acknowledged else None, repeat_count=1 if index == 1 else 0)

    def _snapshot(self) -> dict:
        return dict(as_of=datetime.now(timezone.utc), snapshot_id=f"demo-{self.revision}")

    def get_health(self) -> Health:
        return Health(status="ok", model_ready=False, checked_at=datetime.now(timezone.utc))

    def list_patients(self, filters: dict, cursor: str | None = None) -> Listing[PatientSummary]:
        patients = []
        for original in self.patients.values():
            p = original.model_copy(deep=True)
            events = [a for a in self.alerts.values() if a.patient_id == p.id]
            p.latest_alert_id = max(events, key=lambda a: a.occurred_at).id if events else None
            p.unacknowledged_alert_count = sum(a.status == "unacknowledged" for a in events)
            if filters.get("query", "").lower() not in f"{p.id} {p.bed}".lower():
                continue
            if filters.get("risk_level") and p.prediction.risk_level != filters["risk_level"]:
                continue
            if filters.get("assignee") and p.assignee != filters["assignee"]:
                continue
            if filters.get("unacknowledged_only") and not p.unacknowledged_alert_count:
                continue
            patients.append(PatientSummary.model_validate(p.model_dump()))
        ids = {p.id for p in patients}
        events = [a for a in self.alerts.values() if a.patient_id in ids]
        unacked = [a for a in events if a.status == "unacknowledged"]
        summary = Summary(scope="filtered" if any(filters.values()) else "global", total=len(patients),
            high=sum(p.prediction.risk_level == "high" for p in patients),
            warning=sum(p.prediction.risk_level == "warning" for p in patients),
            unavailable_count=sum(p.prediction.risk_level == "unavailable" for p in patients),
            unacknowledged_alert_count=len(unacked),
            unacknowledged_high_count=sum(a.risk_level == "high" for a in unacked),
            oldest_unacknowledged_at=min((a.occurred_at for a in unacked), default=None))
        patients.sort(key=lambda p: ({"high": 0, "warning": 1, "unavailable": 2, "low": 3}[p.prediction.risk_level],
                                     -(p.unacknowledged_alert_count or 0), p.bed))
        return Listing[PatientSummary](items=patients, summary=summary, **self._snapshot())

    def get_patient(self, patient_id: str) -> Detail:
        if patient_id not in self.patients:
            raise ServiceError("환자를 찾을 수 없습니다.", status=404)
        return Detail(item=self.patients[patient_id].model_copy(deep=True), **self._snapshot())

    def list_alerts(self, filters: dict, cursor: str | None = None) -> Listing[AlertEvent]:
        items = []
        for a in self.alerts.values():
            if filters.get("patient_id") and a.patient_id != filters["patient_id"]:
                continue
            if filters.get("status") and a.status != filters["status"]:
                continue
            if filters.get("assignee") and a.assignee != filters["assignee"]:
                continue
            if filters.get("query", "").lower() not in f"{a.patient_id} {a.bed}".lower():
                continue
            if filters.get("from") and a.occurred_at < datetime.fromisoformat(filters["from"]):
                continue
            if filters.get("to") and a.occurred_at >= datetime.fromisoformat(filters["to"]):
                continue
            items.append(a.model_copy(deep=True))
        items.sort(key=lambda a: a.occurred_at, reverse=True)
        summary = Summary(scope="filtered" if any(filters.values()) else "global", total=len(items),
            unacknowledged_alert_count=sum(a.status == "unacknowledged" for a in items),
            acknowledged_count=sum(a.status == "acknowledged" for a in items),
            recorded_count=sum(bool(a.records) for a in items))
        return Listing[AlertEvent](items=items, summary=summary, **self._snapshot())

    def acknowledge_alert(self, alert_id: str) -> AlertEvent:
        if alert_id not in self.alerts:
            raise ServiceError("경보를 찾을 수 없습니다.", status=404)
        a = self.alerts[alert_id]
        if a.status == "unacknowledged":
            a.status, a.acknowledged_by = "acknowledged", "데모 사용자"
            a.acknowledged_at = datetime.now(timezone.utc)
            self.revision += 1
        return a.model_copy(deep=True)

    def save_record(self, alert_id: str, draft: RecordDraft, key: str) -> CareRecord:
        if key in self.submissions:
            previous_alert, previous_draft, record = self.submissions[key]
            if previous_alert != alert_id or previous_draft != draft:
                raise ServiceError("동일 제출 키의 내용이 다릅니다.", status=409)
            return record.model_copy(deep=True)
        if alert_id not in self.alerts:
            raise ServiceError("경보를 찾을 수 없습니다.", status=404)
        if self.alerts[alert_id].status != "acknowledged":
            raise ServiceError("먼저 경보를 확인하세요.", status=409)
        record = CareRecord(id=str(uuid4()), alert_id=alert_id, author="데모 사용자",
                            saved_at=datetime.now(timezone.utc), **draft.model_dump())
        self.alerts[alert_id].records.append(record)
        self.submissions[key] = (alert_id, draft.model_copy(deep=True), record.model_copy(deep=True))
        self.revision += 1
        return record.model_copy(deep=True)
