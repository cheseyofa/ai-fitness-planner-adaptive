from datetime import datetime, timedelta
from collections.abc import Iterable

from ..models.base import as_utc
from ..models.workout import TrainingLoadResult, WorkoutSession


def session_load(session: WorkoutSession) -> float | None:
    if not session.completed:
        return 0.0
    if session.session_rpe is None or session.duration_minutes is None:
        return None
    return session.session_rpe * session.duration_minutes


def training_volume(session: WorkoutSession) -> float:
    if not session.completed:
        return 0.0
    return sum(s.weight * s.reps for e in session.exercises for s in e.sets
               if s.completed and s.weight is not None)


def calculate_training_load(
    sessions: Iterable[WorkoutSession], *, user_id: str, as_of: datetime,
    history_complete: bool = False,
) -> TrainingLoadResult:
    """最近七个 24 小时区间，权重依次为 1、6/7、…、1/7。"""
    now = as_utc(as_of)
    result = TrainingLoadResult(user_id=user_id, as_of=now, recent_load=0, total_volume=0,
                                session_count=0, missing_load_sessions=0,
                                missing_weight_sets=0, history_complete=history_complete)
    for session in sessions:
        age = now - session.date
        if session.user_id != user_id or not session.completed or not timedelta(0) <= age < timedelta(days=7):
            continue
        result.session_count += 1
        load = session_load(session)
        if load is None:
            result.missing_load_sessions += 1
        else:
            weighted = load * (7 - age.days) / 7
            result.recent_load += weighted
            focus = session.focus or "未分类"
            result.load_by_focus[focus] = result.load_by_focus.get(focus, 0) + weighted
        result.total_volume += training_volume(session)
        for exercise in session.exercises:
            muscle = exercise.target_muscle or "未分类"
            for item in exercise.sets:
                if not item.completed:
                    continue
                if item.weight is None:
                    result.missing_weight_sets += 1
                else:
                    result.volume_by_muscle[muscle] = result.volume_by_muscle.get(muscle, 0) + item.weight * item.reps
    return result
