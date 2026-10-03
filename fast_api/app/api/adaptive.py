from datetime import datetime,timezone,timedelta
from uuid import uuid4
from fastapi import APIRouter,HTTPException
from pydantic import Field
from ..models.base import FitnessModel,as_utc
from ..models.recovery import RecoveryInput
from ..models.workout import WorkoutSession
from ..models.feedback import WorkoutFeedback
from ..services.storage import store
from ..services.recovery_context import collect_recovery,load_history,compute_readiness
from ..services.today_workflow import generate_today
from ..services.memory_service import refresh_memory

adaptive=APIRouter()


class TodayRequest(FitnessModel):
    user_id: str = Field(min_length=1)
    use_llm: bool = True


async def profile_required(user_id: str) -> dict:
    rows=await store.find("user_profiles",{"user_id":user_id},limit=1)
    if not rows: raise HTTPException(404,"请先创建个人资料。")
    return rows[0]


@adaptive.post("/recovery/")
async def save_recovery(data: RecoveryInput) -> dict:
    profile=await profile_required(data.user_id)
    now=datetime.now(timezone.utc)
    if any(item and item.date>now for item in (data.sleep,data.hrv)):
        raise HTTPException(422,"恢复记录时间不能晚于当前时间。")
    await store.save("recovery_records",{"user_id":data.user_id,"day":now.astimezone(timezone(timedelta(hours=8))).date().isoformat()},
                     {"user_id":data.user_id,"date":now,"input":data.model_dump()})
    return await recovery_result(data.user_id,profile)


async def recovery_result(user_id: str,profile: dict) -> dict:
    state={"user_id":user_id,"user_profile":profile,"evaluation_time":datetime.now(timezone.utc).isoformat(),"warnings":[]}
    state.update(await collect_recovery(state));state.update(await load_history(state));state.update(compute_readiness(state))
    return {**state["readiness"],"input":state["recovery_input"],"warnings":state["warnings"]}


@adaptive.get("/recovery/{user_id}")
async def get_recovery(user_id: str) -> dict:
    return await recovery_result(user_id,await profile_required(user_id))


@adaptive.post("/workouts/today/")
async def today(data: TodayRequest) -> dict:
    return await generate_today(data.user_id,use_llm=data.use_llm)


@adaptive.get("/workouts/today/{user_id}")
async def latest_today(user_id: str) -> dict:
    rows=await store.find("workout_plans",{"user_id":user_id},limit=1)
    if not rows: raise HTTPException(404,"还没有训练计划，请先生成今日训练。")
    return rows[0]


@adaptive.post("/workouts/session/")
async def save_session(data: WorkoutSession) -> dict:
    await profile_required(data.user_id)
    if data.date>datetime.now(timezone.utc): raise HTTPException(422,"训练时间不能晚于当前时间。")
    identifier=uuid4().hex
    await store.save("workout_sessions",{"user_id":data.user_id,"workout_id":identifier},
        {**data.model_dump(),"workout_id":identifier})
    return {"workout_id":identifier,"message":"训练记录已保存。"}


@adaptive.get("/workouts/history/{user_id}")
async def history(user_id: str) -> dict:
    return {"sessions":await store.find("workout_sessions",{"user_id":user_id},limit=100)}


@adaptive.post("/feedback/")
async def feedback(data: WorkoutFeedback) -> dict:
    plans=await store.find("workout_plans",{"user_id":data.user_id,"workout_id":data.workout_id},limit=1)
    if not plans: raise HTTPException(404,"未找到属于当前用户的训练计划。")
    if data.date>datetime.now(timezone.utc): raise HTTPException(422,"反馈时间不能晚于当前时间。")
    if data.completed and plans[0]["workout_plan"].get("rest_day"):
        raise HTTPException(422,"休息安排不能记为已完成训练。")
    allowed={e["exercise_name"]:e for d in plans[0]["workout_plan"].get("weekly_schedule",[]) for e in d.get("exercises",[])}
    for exercise in data.exercises:
        if exercise.exercise_name not in allowed: raise HTTPException(422,"反馈中包含本次计划以外的动作。")
        exercise.target_muscle=allowed[exercise.exercise_name]["target_muscle"]
    identity={"user_id":data.user_id,"workout_id":data.workout_id}
    # Idempotent upserts: a retry after a partial write safely completes both records.
    await store.save("workout_feedback",identity,data.model_dump())
    await store.save("workout_sessions",identity,{**identity,"date":data.date,"focus":"全身",
        "exercises":[e.model_dump() for e in data.exercises],"session_rpe":data.session_rpe,
        "duration_minutes":data.duration_minutes,"completed":data.completed})
    warnings=[]
    try: await refresh_memory(data.user_id)
    except Exception: warnings.append("反馈已保存，记忆摘要将在下次读取时更新。")
    return {"message":"反馈已保存，下次规划会读取本次训练记录。","warnings":warnings}


@adaptive.get("/memory/{user_id}")
async def memory(user_id: str) -> dict:
    await profile_required(user_id)
    return await refresh_memory(user_id)
