import unittest
from unittest.mock import patch,AsyncMock,Mock
from fast_api.app.agents import workout_planner_agent as planner
from fast_api.app.services.exercise_provider import LocalExerciseProvider


class PlannerFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_invented_exercise_rejected(self):
        candidates=await LocalExerciseProvider().search_exercises()
        fake=Mock();fake.ainvoke=AsyncMock(return_value={"parsed":planner.Selection(exercise_ids=["invented"]),"raw":Mock(usage_metadata={"total_tokens":100})})
        with patch.object(planner,'chat_key',return_value='test-only'),patch.object(planner,'create_chat_model'),patch.object(planner,'structured_chat',return_value=fake):
            plan,warnings=await planner.plan_from_candidates({},candidates)
        self.assertTrue(warnings)
        self.assertFalse(plan['generation_metrics']['structured_output_valid'])
        self.assertTrue(all(e['exercise_id'] in {c['id'] for c in candidates} for d in plan['weekly_schedule'] for e in d['exercises']))

    async def test_llm_error_retains_plan(self):
        candidates=await LocalExerciseProvider().search_exercises()
        fake=Mock();fake.ainvoke=AsyncMock(side_effect=RuntimeError('offline'))
        with patch.object(planner,'chat_key',return_value='test-only'),patch.object(planner,'create_chat_model'),patch.object(planner,'structured_chat',return_value=fake):
            plan,warnings=await planner.plan_from_candidates({},candidates)
        self.assertTrue(plan['weekly_schedule'])
        self.assertTrue(warnings)
