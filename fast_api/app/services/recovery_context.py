from datetime import datetime, timedelta
from typing import Any
from langsmith import traceable
from ..models.recovery import RecoveryInput
from ..models.workout import WorkoutSession
from .recovery_provider import ManualRecoveryProvider
from .readiness_engine import ReadinessConfig, calculate_readiness
from .training_load import calculate_training_load
from .storage import store


@traceable(name="recovery_collector")
async def collect_recovery(state: dict[str, Any]) -> dict[str, Any]:
    now = datetime.fromisoformat(state["evaluation_time"])
    warnings = list(state.get("warnings", []))
    try:
        data = await ManualRecoveryProvider().get_recovery(state["user_id"], now)
    except Exception:
        data = RecoveryInput(user_id=state["user_id"])
        warnings.append("恢复记录暂时无法读取，已使用保守评分。")
    profile = state.get("user_profile") or {}
    if data.hrv and data.hrv.baseline_hrv_ms is None and profile.get("baseline_hrv"):
        data.hrv.baseline_hrv_ms = profile["baseline_hrv"]
    if data.baseline_resting_hr is None:
        data.baseline_resting_hr = profile.get("baseline_resting_hr")
    try:
        feedback=await store.find("workout_feedback",{"user_id":state["user_id"],
            "date":{"$gt":now-timedelta(hours=36),"$lte":now}},limit=10)
        soreness=dict(data.soreness or {})
        for entry in feedback:
            for muscle,value in (entry.get("soreness_after") or {}).items():
                soreness[muscle]=max(soreness.get(muscle,0),value)
        data.soreness=soreness or None
    except Exception:
        warnings.append("近期反馈暂不可用，本次仅使用已读取的恢复数据。")
    return {"recovery_input": data.model_dump(mode="json"), "sleep_data": data.sleep.model_dump(mode="json") if data.sleep else None,
            "hrv_data": data.hrv.model_dump(mode="json") if data.hrv else None,
            "resting_hr_data": {"value": data.resting_hr, "baseline": data.baseline_resting_hr},
            "soreness_data": data.soreness or {}, "subjective_fatigue": data.subjective_fatigue,
            "warnings": warnings}


@traceable(name="training_history_loader")
async def load_history(state: dict[str, Any]) -> dict[str, Any]:
    now = datetime.fromisoformat(state["evaluation_time"])
    warnings = list(state.get("warnings", []))
    try:
        rows = await store.find("workout_sessions", {"user_id": state["user_id"],
            "date": {"$gt": now-timedelta(days=7), "$lte": now}}, limit=201)
        sessions = [WorkoutSession.model_validate({k:v for k,v in row.items()
                    if k in WorkoutSession.model_fields}) for row in rows[:200]]
        # A successful query alone does not prove the user logged every workout.
        complete = bool((state.get("user_profile") or {}).get("history_complete", False)) and len(rows) <= 200
    except Exception:
        sessions, complete = [], False
        warnings.append("训练历史暂时无法读取，本次不推断为零负荷。")
    load = calculate_training_load(sessions, user_id=state["user_id"], as_of=now, history_complete=complete)
    return {"training_history": [s.model_dump(mode="json") for s in sessions],
            "training_load_result": load.model_dump(mode="json"), "recent_training_load": load.recent_load,
            "warnings": warnings}


def compute_readiness(state: dict[str, Any]) -> dict[str, Any]:
    from ..models.workout import TrainingLoadResult
    profile = state.get("user_profile") or {}
    config = ReadinessConfig.from_env()
    if profile.get("normal_sleep_duration"):
        config = ReadinessConfig.model_validate({**config.model_dump(), "baseline_sleep_hours": profile["normal_sleep_duration"]})
    result = calculate_readiness(RecoveryInput.model_validate(state["recovery_input"]),
        as_of=datetime.fromisoformat(state["evaluation_time"]),
        training_load=TrainingLoadResult.model_validate(state["training_load_result"]), config=config)
    return {"readiness": result.model_dump(), "readiness_score": result.score,
            "recovery_level": result.level, "recovery_reasons": result.reasons}
