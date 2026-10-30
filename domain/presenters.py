"""Pure, timezone-aware presentation helpers."""
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
RISK_LABELS = {"high": "! 고위험", "warning": "△ 주의", "low": "— 낮음", "unavailable": "예측 불가"}
TRENDS = {"rising": "↗ 상승", "stable": "→ 유지", "falling": "↘ 하락", None: "미제공"}


def time_label(value: datetime | None, full: bool = False) -> str:
    """Distinguish missing time from an actual timestamp."""
    return value.astimezone(KST).strftime("%m.%d %H:%M" if full else "%H:%M") if value else "—"


def score_label(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f} / 100"
