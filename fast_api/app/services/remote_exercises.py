import json
import os
import httpx
from .exercise_provider import ExerciseProvider, CATALOG
from ..tools.mcp_client import MCPClient

ALIASES={"Squat":"squat","Bodyweight squat":"squat","Wall push-up":"wall_push","Glute bridge":"bridge",
         "Calf raises":"calf","Bird dog":"bird_dog","Dead bug":"dead_bug","Dumbbell row":"db_row",
         "Dumbbell curl":"db_curl","Dumbbell shoulder press":"db_press","Resistance band row":"band_row"}


def normalize(rows: list[dict], source: str, equipment: list[str] | None, target: str | None, limit: int) -> list[dict]:
    """Only verified local translations/safety metadata are eligible for planning."""
    found=[]
    for row in rows:
        names=[row.get("name","")]+[t.get("name","") for t in row.get("translations",[])]
        match=next((e for e in CATALOG if e["name"] in names or any(ALIASES.get(n)==e["id"] for n in names)),None)
        if match and (not target or match["muscle"]==target) and set(match["equipment"]).issubset(set(equipment or [])|{"bodyweight"}):
            if not any(e["id"]==match["id"] for e in found):
                found.append({**match,"source":source,"remote_id":row.get("id")})
    return found[:limit]


class WgerExerciseProvider(ExerciseProvider):
    async def search_exercises(self,target_muscle=None,equipment=None,difficulty=None,limit=10) -> list[dict]:
        url=os.getenv("WGER_BASE_URL") or "https://wger.de"
        headers={}
        if os.getenv("WGER_API_KEY"): headers["Authorization"]="Token "+os.environ["WGER_API_KEY"]
        async with httpx.AsyncClient(timeout=8) as client:
            response=await client.get(url.rstrip("/")+"/api/v2/exerciseinfo/",params={"limit":100},headers=headers)
            response.raise_for_status()
        return normalize(response.json()["results"],"wger",equipment,target_muscle,limit)


class WgerMCPProvider(ExerciseProvider):
    async def search_exercises(self,target_muscle=None,equipment=None,difficulty=None,limit=10) -> list[dict]:
        arguments={"target_muscle":target_muscle,"equipment":equipment,"difficulty":difficulty,"limit":limit}
        result=await MCPClient(os.getenv("WGER_MCP_URL",""),os.getenv("WGER_MCP_TOKEN","")).call_tool(
            os.getenv("WGER_MCP_SEARCH_TOOL","search_exercises"),arguments)
        data=result.get("structuredContent")
        if data is None:
            data=json.loads(next(item["text"] for item in result.get("content",[]) if item.get("type")=="text"))
        rows=data if isinstance(data,list) else data.get("results",data.get("exercises",[]))
        return normalize(rows,"mcp",equipment,target_muscle,limit)
