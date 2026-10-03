from ..agents.plan_modifier_agent import modify_plan, rest_plan
from ..agents.workout_planner_agent import plan_from_candidates
from ..models.recovery import ReadinessResult
from .exercise_provider import LocalExerciseProvider, safe_candidates


async def plan_adaptive(state: dict, *, use_llm: bool = True) -> dict:
    readiness=ReadinessResult.model_validate(state["readiness"])
    if readiness.level == "VERY_LOW":
        plan=rest_plan("恢复状态很低，今天暂停高强度训练。")
        return {"workout_plan":plan,"base_workout_plan":None,"plan_adjustments":[{"reason":plan["adjustment_summary"]}],"exercise_candidates":[]}
    working={**state,**(await retrieve_candidates(state))}
    working.update(await build_base(working,use_llm=use_llm))
    working.update(adjust_base(working))
    return {key:working[key] for key in ("base_workout_plan","workout_plan","plan_adjustments","exercise_candidates","tool_traces","warnings")}


async def retrieve_candidates(state: dict) -> dict:
    profile=state.get("user_profile") or {}
    from ..tools.exercise_tools import retrieve_exercises
    candidates,traces=await retrieve_exercises(profile)
    candidates=safe_candidates(candidates,profile,state.get("soreness_data") or {})
    # Avoid repeating a heavily loaded muscle within the preceding 24 hours.
    from datetime import datetime, timedelta
    now=datetime.fromisoformat(state["evaluation_time"])
    from ..models.base import as_utc
    recent_muscles={e.get("target_muscle") for s in state.get("training_history",[])
                    if s.get("completed") and s.get("session_rpe",0) is not None and (s.get("session_rpe") or 0)>=7
                    and now-as_utc(datetime.fromisoformat(s["date"]))<timedelta(hours=24)
                    for e in s.get("exercises",[]) if any(x.get("completed") for x in e.get("sets",[]))}
    candidates=[e for e in candidates if e["muscle"] not in recent_muscles]
    return {"exercise_candidates":candidates,"tool_traces":traces}


async def build_base(state: dict, *, use_llm: bool=True) -> dict:
    candidates=state.get("exercise_candidates",[])
    if not candidates:
        plan=rest_plan("当前伤痛、酸痛或近期训练限制下，没有合适的候选动作，今天先休息。")
        return {"base_workout_plan":plan,"warnings":state.get("warnings",[])}
    base,warnings=await plan_from_candidates(state.get("user_profile") or {},candidates,use_llm=use_llm)
    return {"base_workout_plan":base,"warnings":state.get("warnings",[])+warnings}


def adjust_base(state: dict) -> dict:
    base=state["base_workout_plan"]
    readiness=ReadinessResult.model_validate(state["readiness"])
    adjusted,changes=modify_plan(base,readiness)
    return {"workout_plan":adjusted,"plan_adjustments":changes}
