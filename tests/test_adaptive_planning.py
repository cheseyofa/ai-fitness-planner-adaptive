import unittest
from datetime import datetime, timezone
from fast_api.app.models.recovery import RecoveryInput
from fast_api.app.services.readiness_engine import calculate_readiness
from fast_api.app.services.adaptive_planning import plan_adaptive
from fast_api.app.services.exercise_provider import LocalExerciseProvider,safe_candidates


class AdaptiveTests(unittest.IsolatedAsyncioTestCase):
    def state(self,fatigue=0):
        now=datetime.now(timezone.utc)
        r=calculate_readiness(RecoveryInput(user_id="x",subjective_fatigue=fatigue),as_of=now)
        return {"user_id":"x","evaluation_time":now.isoformat(),"readiness":r.model_dump(),"user_profile":{},"training_history":[]}

    async def test_low_reduces_sets(self):
        result=await plan_adaptive(self.state(),use_llm=False)
        self.assertLess(result["workout_plan"]["adjusted_volume"], result["workout_plan"]["original_volume"])
        self.assertTrue(all(e["target_rpe"]<=4 for d in result["workout_plan"]["weekly_schedule"] for e in d["exercises"]))

    async def test_very_low_rest(self):
        result=await plan_adaptive(self.state(9),use_llm=False)
        self.assertTrue(result["workout_plan"]["rest_day"])

    async def test_injury_and_soreness(self):
        candidates=await LocalExerciseProvider().search_exercises()
        filtered=safe_candidates(candidates,{"injuries":["肩部"]},{"legs":8})
        self.assertTrue(all(e["muscle"]!="legs" and "shoulder" not in e["avoid"] for e in filtered))

    async def test_unknown_injury_rest(self):
        state=self.state();state["user_profile"]={"injuries":["不明疼痛"]}
        self.assertTrue((await plan_adaptive(state,use_llm=False))["workout_plan"]["rest_day"])

    async def test_no_unavailable_equipment(self):
        candidates=await LocalExerciseProvider().search_exercises(equipment=["bodyweight"])
        self.assertTrue(all(e["equipment"]==["bodyweight"] for e in candidates))
