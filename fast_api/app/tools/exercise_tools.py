import os
import time
from langsmith import traceable
from ..services.exercise_provider import LocalExerciseProvider
from ..services.remote_exercises import WgerExerciseProvider,WgerMCPProvider


@traceable(name="exercise_retrieval",run_type="tool")
async def retrieve_exercises(profile: dict) -> tuple[list[dict],list[dict]]:
    provider=os.getenv("EXERCISE_PROVIDER","local")
    chain=([WgerMCPProvider(),WgerExerciseProvider()] if provider=="mcp" else
           [WgerExerciseProvider()] if provider=="wger" else [])+[LocalExerciseProvider()]
    traces=[]
    for service in chain:
        started=time.perf_counter()
        try:
            rows=await service.search_exercises(equipment=profile.get("equipment_available"),difficulty=profile.get("training_experience"))
            status="success" if rows else "empty"
        except Exception:
            rows=[];status="failed"
        traces.append({"provider":type(service).__name__,"status":status,"latency_ms":round((time.perf_counter()-started)*1000,2)})
        if rows: return rows,traces
    return [],traces
