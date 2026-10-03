import os
import unittest
from unittest.mock import patch,AsyncMock
from fast_api.app.tools.video_tools import attach_videos
from fast_api.app.services.video_provider import YouTubeVideoProvider


class VideoTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_preserves_plan(self):
        with patch.dict(os.environ,{"VIDEO_PROVIDER":"youtube"}),patch.object(YouTubeVideoProvider,"search_exercise_video",AsyncMock(side_effect=RuntimeError())):
            state=await attach_videos({"workout_plan":{"weekly_schedule":[{"exercises":[{"exercise_name":"深蹲","sets":2}]}]}})
        self.assertEqual(state["workout_plan"]["weekly_schedule"][0]["exercises"][0]["sets"],2)
        self.assertFalse(state["exercise_videos"])

    async def test_mock_no_fabricated_link(self):
        with patch.dict(os.environ,{"VIDEO_PROVIDER":"mock"}):
            result=await attach_videos({"workout_plan":{"weekly_schedule":[]}})
        self.assertEqual(result["exercise_videos"],[])
