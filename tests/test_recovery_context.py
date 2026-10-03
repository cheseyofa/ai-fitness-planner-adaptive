import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fast_api.app.services import recovery_context as context


class RecoveryContextTests(unittest.IsolatedAsyncioTestCase):
    def state(self):
        return {"user_id":"test", "user_profile":{}, "evaluation_time":datetime.now(timezone.utc).isoformat(), "warnings":[]}

    async def test_missing_data_retains_score(self):
        state=self.state()
        with patch.object(context.store,"find",AsyncMock(return_value=[])):
            state.update(await context.collect_recovery(state))
            state.update(await context.load_history(state))
        result=context.compute_readiness(state)
        self.assertEqual(result["recovery_level"],"LOW")
        self.assertEqual(result["readiness_score"],50)

    async def test_provider_failure_fallback(self):
        state=self.state()
        with patch.object(context.store,"find",AsyncMock(side_effect=RuntimeError("offline"))):
            state.update(await context.collect_recovery(state))
            state.update(await context.load_history(state))
        self.assertEqual(len(state["warnings"]),3)
        self.assertEqual(context.compute_readiness(state)["recovery_level"],"LOW")

    async def test_severe_fatigue(self):
        state=self.state()
        with patch.object(context.store,"find",AsyncMock(side_effect=[[{"input":{"user_id":"test","subjective_fatigue":9}}],[],[]])):
            state.update(await context.collect_recovery(state))
            state.update(await context.load_history(state))
        self.assertEqual(context.compute_readiness(state)["recovery_level"],"VERY_LOW")
