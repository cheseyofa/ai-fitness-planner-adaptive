from datetime import datetime,timezone
from .storage import store


async def refresh_memory(user_id: str) -> dict:
    profiles=await store.find("user_profiles",{"user_id":user_id},limit=1)
    history=await store.find("workout_sessions",{"user_id":user_id},limit=30)
    feedback=await store.find("workout_feedback",{"user_id":user_id},limit=10)
    profile=profiles[0] if profiles else {}
    memory={"user_id":user_id,"date":datetime.now(timezone.utc),
        "profile":{key:profile.get(key) for key in ("fitness_goal","injuries","equipment_available")},
        "preferences":{key:profile.get(key,[]) for key in ("preferred_exercises","disliked_exercises")},
        "training":{"recent_sessions":len(history),"completed_sessions":sum(bool(s.get("completed")) for s in history),
                    "recent_loads":[(s.get("session_rpe") or 0)*(s.get("duration_minutes") or 0) for s in history if s.get("completed")],
                    "recent_exercise_names":list(dict.fromkeys(e["exercise_name"] for s in history for e in s.get("exercises",[])))},
        "recovery":{"baseline_hrv":profile.get("baseline_hrv"),"normal_sleep_duration":profile.get("normal_sleep_duration",8),
                    "recent_difficulty":[f["perceived_difficulty"] for f in feedback if f.get("perceived_difficulty") is not None]},
        "recent_feedback":feedback[:3]}
    await store.save("user_memory",{"user_id":user_id},memory)
    return memory
