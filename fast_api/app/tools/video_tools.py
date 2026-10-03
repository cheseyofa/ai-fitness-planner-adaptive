import asyncio
import os
from langsmith import traceable
from ..services.video_provider import MockVideoProvider,YouTubeVideoProvider


@traceable(name="video_retrieval",run_type="tool")
async def attach_videos(state: dict) -> dict:
    plan=state.get("workout_plan") or {}
    exercises=[e for d in plan.get("weekly_schedule",[]) for e in d.get("exercises",[])]
    service=YouTubeVideoProvider() if os.getenv("VIDEO_PROVIDER","mock")=="youtube" else MockVideoProvider()
    warnings=list(state.get("warnings",[]))
    async def fetch(e: dict) -> list[dict]:
        try: return await service.search_exercise_video(e["exercise_name"],1)
        except Exception: return []
    videos=await asyncio.gather(*(fetch(e) for e in exercises))
    for e,items in zip(exercises,videos):
        e["videos"]=items
        e["video_url"]=items[0]["url"] if items else None
    if exercises and not any(videos): warnings.append("暂未获取教学视频，训练安排不受影响。")
    return {"workout_plan":plan,"exercise_videos":[v for items in videos for v in items],"warnings":warnings}
