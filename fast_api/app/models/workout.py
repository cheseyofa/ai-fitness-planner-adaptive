from datetime import datetime

from pydantic import Field, field_validator

from .base import FitnessModel, as_utc
from .recovery import Rating


class WorkoutSet(FitnessModel):
    weight: float | None = Field(default=None, ge=0, description="千克")
    reps: int = Field(ge=0)
    rpe: Rating | None = None
    completed: bool = True


class ExerciseLog(FitnessModel):
    exercise_name: str = Field(min_length=1)
    target_muscle: str | None = Field(default=None, min_length=1)
    sets: list[WorkoutSet] = Field(default_factory=list)


class WorkoutSession(FitnessModel):
    user_id: str = Field(min_length=1)
    date: datetime
    focus: str | None = Field(default=None, min_length=1)
    exercises: list[ExerciseLog] = Field(default_factory=list)
    session_rpe: Rating | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    completed: bool = True

    _utc = field_validator("date")(as_utc)


class TrainingLoadResult(FitnessModel):
    user_id: str
    as_of: datetime
    recent_load: float = Field(ge=0)
    total_volume: float = Field(ge=0, description="已知重量的训练总量，千克×次数")
    load_by_focus: dict[str, float] = Field(default_factory=dict)
    volume_by_muscle: dict[str, float] = Field(default_factory=dict)
    session_count: int = Field(ge=0)
    missing_load_sessions: int = Field(ge=0)
    missing_weight_sets: int = Field(ge=0)
    history_complete: bool

    _utc = field_validator("as_of")(as_utc)
