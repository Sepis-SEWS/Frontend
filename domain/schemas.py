"""Strictly validated dashboard contracts shared by API and synthetic demo."""
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

RiskLevel = Literal["high", "warning", "low", "unavailable"]
Score = float | None


class Model(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class Prediction(Model):
    risk_score: Score = Field(ge=0, le=1)
    risk_level: RiskLevel
    predicted_at: AwareDatetime | None
    model_version: str
    threshold_version: str
    prediction_id: str | None = None
    calibrated_probability: Score = Field(default=None, ge=0, le=1)
    calibration_available: bool = False
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def consistency(self) -> "Prediction":
        if (self.risk_score is None) != (self.risk_level == "unavailable"):
            raise ValueError("null score must have unavailable risk level")
        if self.risk_score is None and not self.unavailable_reason:
            raise ValueError("unavailable prediction needs a reason")
        if self.risk_score is not None and self.predicted_at is None:
            raise ValueError("prediction needs a timestamp")
        if self.calibration_available != (self.calibrated_probability is not None):
            raise ValueError("calibration availability and value disagree")
        return self


class PatientSummary(Model):
    id: str
    bed: str
    assignee: str
    icu_id: str = "ICU-A"
    last_observed_at: AwareDatetime | None
    prediction: Prediction
    data_delayed: bool
    delay_reason: str | None = None
    trend: Literal["rising", "stable", "falling"] | None = None
    latest_alert_id: str | None = None
    unacknowledged_alert_count: int | None = Field(default=None, ge=0)


class Observation(Model):
    feature_name: str
    value: float | None
    unit: str
    observed_at: AwareDatetime | None


class TimePoint(Model):
    observed_at: AwareDatetime
    predicted_at: AwareDatetime | None = None
    risk_score: Score = Field(default=None, ge=0, le=1)
    hr: float | None = None
    map: float | None = None
    lactate: float | None = None


class Contribution(Model):
    name: str
    value: float | None = None
    unit: str = ""
    contribution: float


class Explanation(Model):
    available: bool
    method: str | None = None
    model_version: str | None = None
    prediction_id: str | None = None
    output_scale: str | None = None
    features: list[Contribution] = Field(default_factory=list)
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def consistency(self) -> "Explanation":
        if not self.available and (self.features or not self.unavailable_reason):
            raise ValueError("unavailable explanation needs an empty list and reason")
        return self


class SOFA(Model):
    available: bool = False
    total: float | None = None
    components: dict = Field(default_factory=dict)
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def consistency(self) -> "SOFA":
        if not self.available and self.total is not None:
            raise ValueError("incomplete SOFA cannot have a total")
        return self


class PatientDetail(PatientSummary):
    observations: list[Observation]
    series: list[TimePoint]
    explanation: Explanation
    sofa: SOFA


class RecordDraft(Model):
    model_config = ConfigDict(str_strip_whitespace=True)
    assessment: str = Field(min_length=1, max_length=2000)
    action: str = Field(min_length=1, max_length=2000)


class CareRecord(RecordDraft):
    id: str
    alert_id: str
    author: str
    saved_at: AwareDatetime


class AlertEvent(Model):
    id: str
    patient_id: str
    bed: str | None = None
    assignee: str | None = None
    risk_score: float = Field(ge=0, le=1)
    risk_level: Literal["high", "warning", "low"]
    model_version: str
    threshold_version: str
    occurred_at: AwareDatetime
    status: Literal["unacknowledged", "acknowledged"]
    acknowledged_by: str | None = None
    acknowledged_at: AwareDatetime | None = None
    repeat_count: int = Field(default=0, ge=0)
    records: list[CareRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistency(self) -> "AlertEvent":
        acknowledged = self.status == "acknowledged"
        if acknowledged != (self.acknowledged_at is not None and bool(self.acknowledged_by)):
            raise ValueError("acknowledgement fields disagree")
        if not acknowledged and (self.acknowledged_at or self.acknowledged_by or self.records):
            raise ValueError("unacknowledged alert cannot contain acknowledgement or records")
        if any(record.alert_id != self.id for record in self.records):
            raise ValueError("record belongs to another alert")
        return self


class Summary(Model):
    scope: Literal["global", "filtered"]
    total: int = Field(ge=0)
    high: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    unavailable_count: int = Field(default=0, ge=0)
    unacknowledged_alert_count: int = Field(default=0, ge=0)
    unacknowledged_high_count: int = Field(default=0, ge=0)
    oldest_unacknowledged_at: AwareDatetime | None = None
    acknowledged_count: int = Field(default=0, ge=0)
    recorded_count: int = Field(default=0, ge=0)


T = TypeVar("T")


class Listing(Model, Generic[T]):
    items: list[T]
    as_of: AwareDatetime
    snapshot_id: str | None = None
    next_cursor: str | None = None
    summary: Summary


class Detail(Model):
    item: PatientDetail
    as_of: AwareDatetime
    snapshot_id: str | None = None


class Health(Model):
    status: Literal["ok", "degraded", "unavailable"]
    model_ready: bool
    checked_at: AwareDatetime
