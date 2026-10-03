import os
import unittest
from unittest.mock import AsyncMock,patch
from fast_api.app.tools.exercise_tools import retrieve_exercises
from fast_api.app.services.remote_exercises import WgerExerciseProvider,WgerMCPProvider,normalize


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_and_rest_offline(self):
        with patch.dict(os.environ,{"EXERCISE_PROVIDER":"mcp"}), \
             patch.object(WgerMCPProvider,"search_exercises",AsyncMock(side_effect=RuntimeError())), \
             patch.object(WgerExerciseProvider,"search_exercises",AsyncMock(side_effect=RuntimeError())):
            rows,traces=await retrieve_exercises({})
        self.assertTrue(rows)
        self.assertEqual([t["status"] for t in traces],["failed","failed","success"])

    async def test_unmapped_remote_exercise_excluded(self):
        self.assertEqual(normalize([{"id":1,"name":"Unknown exercise"}],"wger",[],None,10),[])

    async def test_remote_translation_preserves_source(self):
        rows=normalize([{"id":88,"translations":[{"name":"Squat"}]}],"wger",[],None,10)
        self.assertEqual(rows[0]["name"],"徒手深蹲")
        self.assertEqual(rows[0]["remote_id"],88)
