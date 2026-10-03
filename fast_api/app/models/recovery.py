from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from .base import FitnessModel, as_utc

Rating = Annotated[float, Field(ge=0, le=10)]
Positive = Annotated[float, Field(gt=0)]


class SleepData(FitnessModel):
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sleep_duration_hours: float = Field(ge=0, le=24)
    sleep_score: float | None = Field(default=None, ge=0, le=100)
    deep_sleep_minutes: float | None = Field(default=None, ge=0)
    rem_sleep_minutes: float | None = Field(default=None, ge=0)

    _utc = field_validator("date")(as_utc)

    @model_validator(mode="after")
    def check_stages(self) -> "SleepData":
        if (self.deep_sleep_minutes or 0) + (self.rem_sleep_minutes or 0) > self.sleep_duration_hours * 60:
            raise ValueError("深睡与快速眼动睡眠的总时长不能超过睡眠时长")
        return self


class HRVData(FitnessModel):
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hrv_ms: Positive | None = None
    baseline_hrv_ms: Positive | None = None

    _utc = field_validator("date")(as_utc)


class RecoveryInput(FitnessModel):
    user_id: str = Field(min_length=1)
    sleep: SleepData | None = None
    hrv: HRVData | None = None
    resting_hr: Positive | None = None
    baseline_resting_hr: Positive | None = None
    soreness: dict[Annotated[str, Field(min_length=1)], Rating] | None = None
    subjective_fatigue: Rating | None = None


class ReadinessResult(FitnessModel):
    score: float = Field(ge=0, le=100)
    level: Literal["HIGH", "MEDIUM", "LOW", "VERY_LOW"]
    reasons: list[str]
    recommended_volume_multiplier: float = Field(ge=0, le=1)
    recommended_intensity_multiplier: float = Field(ge=0, le=1)
    recommended_rpe_delta: float
    component_scores: dict[str, float] = Field(default_factory=dict)
    data_coverage: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
