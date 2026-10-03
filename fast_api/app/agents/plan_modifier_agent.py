from copy import deepcopy
from math import floor
from ..models.recovery import ReadinessResult


def rest_plan(reason: str) -> dict:
    return {"plan_name":"今日休息安排", "weekly_schedule":[], "rest_day":True,
            "adjustment_summary":reason, "original_volume":0, "adjusted_volume":0,
            "key_principles":["今天暂停高强度训练，记录恢复情况；如有疼痛或明显不适，请寻求专业评估。"]}


def modify_plan(base: dict, readiness: ReadinessResult) -> tuple[dict, list[dict]]:
    if base.get("rest_day"):
        return deepcopy(base),[{"reason":base["adjustment_summary"]}]
    original = sum(e["sets"] for day in base.get("weekly_schedule",[]) for e in day.get("exercises",[]))
    if readiness.level == "VERY_LOW":
        plan=rest_plan("恢复状态很低，今天以休息为主。")
        plan["original_volume"]=original
        return plan,[{"reason":"恢复状态很低，暂停训练。", "before":original,"after":0}]
    plan=deepcopy(base)
    changes=[]
    for day in plan.get("weekly_schedule",[]):
        exercises=[]
        for exercise in day.get("exercises",[]):
            before=exercise["sets"]
            sets=max(0,floor(before*readiness.recommended_volume_multiplier))
            if sets:
                exercise["sets"]=sets
                exercise["target_rpe"]=max(1,min(8,exercise.get("target_rpe",6)+readiness.recommended_rpe_delta))
                exercise["intensity_multiplier"]=readiness.recommended_intensity_multiplier
                exercises.append(exercise)
            changes.append({"exercise_name":exercise["exercise_name"],"before":before,"after":sets,
                            "reason":"按恢复状态调整组数与主观用力程度。"})
        day["exercises"]=exercises
    adjusted=sum(e["sets"] for day in plan.get("weekly_schedule",[]) for e in day["exercises"])
    plan.update(readiness_score=readiness.score,recovery_level=readiness.level,
                original_volume=original,adjusted_volume=adjusted,
                adjustment_summary=f"训练总组数由 {original} 组调整为 {adjusted} 组。")
    return plan,changes
