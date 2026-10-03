from datetime import datetime, timezone
from pydantic import Field,field_validator,model_validator
from .base import FitnessModel,as_utc
from .recovery import Rating
from .workout import ExerciseLog


class WorkoutFeedback(FitnessModel):
    user_id: str = Field(min_length=1)
    workout_id: str = Field(min_length=1)
    date: datetime = Field(default_factory=lambda:datetime.now(timezone.utc))
    completed: bool
    perceived_difficulty: Rating | None = None
    session_rpe: Rating | None = None
    duration_minutes: int | None = Field(default=None,gt=0,le=600)
    soreness_after: dict[str,Rating] = Field(default_factory=dict)
    exercises: list[ExerciseLog] = Field(default_factory=list)
    notes: str = Field(default="",max_length=2000)

    _utc=field_validator("date")(as_utc)

    @model_validator(mode="after")
    def validate_completion(self):
        if self.completed and (self.session_rpe is None or self.duration_minutes is None):
            raise ValueError("完成训练后请填写实际用力程度和训练分钟数")
        return self
