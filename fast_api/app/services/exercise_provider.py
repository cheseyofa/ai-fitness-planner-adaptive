"""Small curated local catalogue: no invented remote IDs or medical claims."""
from abc import ABC, abstractmethod
from typing import Any

CATALOG = [
    {"id":"squat","name":"徒手深蹲","muscle":"legs","equipment":["bodyweight"],"avoid":["knee","hip","back"],"reps":"8–12"},
    {"id":"wall_push","name":"靠墙俯卧撑","muscle":"chest","equipment":["bodyweight"],"avoid":["shoulder","wrist","elbow"],"reps":"8–12"},
    {"id":"bridge","name":"臀桥","muscle":"legs","equipment":["bodyweight"],"avoid":["back","hip"],"reps":"10–12"},
    {"id":"calf","name":"站姿提踵","muscle":"legs","equipment":["bodyweight"],"avoid":["ankle","knee"],"reps":"10–15"},
    {"id":"bird_dog","name":"鸟狗式","muscle":"core","equipment":["bodyweight"],"avoid":["back","knee","wrist","shoulder"],"reps":"每侧 6–8"},
    {"id":"dead_bug","name":"死虫式","muscle":"core","equipment":["bodyweight"],"avoid":["back","hip"],"reps":"每侧 6–8"},
    {"id":"db_row","name":"哑铃俯身划船","muscle":"back","equipment":["dumbbells"],"avoid":["back","shoulder","elbow"],"reps":"8–12"},
    {"id":"db_curl","name":"哑铃弯举","muscle":"arms","equipment":["dumbbells"],"avoid":["elbow","wrist"],"reps":"10–12"},
    {"id":"db_press","name":"哑铃肩上推举","muscle":"shoulders","equipment":["dumbbells"],"avoid":["shoulder","back","elbow"],"reps":"8–10"},
    {"id":"band_row","name":"弹力带划船","muscle":"back","equipment":["resistance_bands"],"avoid":["shoulder","elbow","back"],"reps":"10–12"},
]
MUSCLES = {"legs":"腿部", "chest":"胸部", "back":"背部", "core":"核心", "arms":"手臂", "shoulders":"肩部"}
INJURIES = {"膝":"knee","腰":"back","背":"back","肩":"shoulder","腕":"wrist","肘":"elbow","髋":"hip","踝":"ankle"}


class ExerciseProvider(ABC):
    @abstractmethod
    async def search_exercises(self, target_muscle: str | None = None,
        equipment: list[str] | None = None, difficulty: str | None = None, limit: int = 10) -> list[dict[str, Any]]: ...


class LocalExerciseProvider(ExerciseProvider):
    async def search_exercises(self, target_muscle: str | None = None,
        equipment: list[str] | None = None, difficulty: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        available = set(equipment or []) | {"bodyweight"}
        return [{**e, "source":"local", "difficulty":"beginner"} for e in CATALOG
                if (not target_muscle or e["muscle"] == target_muscle)
                and set(e["equipment"]).issubset(available)][:max(0,min(limit,30))]


def safe_candidates(candidates: list[dict], profile: dict, soreness: dict) -> list[dict]:
    injuries: set[str] = set()
    for item in profile.get("injuries") or []:
        normalized = INJURIES.get(item, item)
        matches = {value for key,value in INJURIES.items() if key in item}
        if normalized in INJURIES.values(): matches.add(normalized)
        if not matches:
            return []  # Unknown injury: do not assume a safe exercise.
        injuries.update(matches)
    blocked = {key for key,value in soreness.items() if value >= 7}
    blocked |= {key for key,label in MUSCLES.items() if label in blocked}
    disliked = set(profile.get("disliked_exercises") or [])
    return [e for e in candidates if not injuries.intersection(e.get("avoid", []))
            and e["muscle"] not in blocked and e["id"] not in disliked and e["name"] not in disliked]
