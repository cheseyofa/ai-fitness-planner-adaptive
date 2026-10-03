from datetime import datetime,timezone
from uuid import uuid4
from langgraph.graph import StateGraph,END
from langsmith import traceable
from fastapi import HTTPException
from .storage import store
from .recovery_context import collect_recovery,load_history,compute_readiness
from .adaptive_planning import plan_adaptive,retrieve_candidates,build_base,adjust_base
from .memory_service import refresh_memory
from ..tools.video_tools import attach_videos


@traceable(name="adaptive_today_workflow")
async def generate_today(user_id: str, *, use_llm: bool=True) -> dict:
    from ..api.langgraph_agents import FitnessState
    profiles=await store.find("user_profiles",{"user_id":user_id},limit=1)
    if not profiles: raise HTTPException(404,"请先创建个人资料。")
    graph=StateGraph(FitnessState)
    graph.add_node("recovery_collector",collect_recovery)
    graph.add_node("training_history_loader",load_history)
    graph.add_node("readiness_engine",compute_readiness)
    async def planner(state): return await build_base(state,use_llm=use_llm)
    async def rest(state): return await plan_adaptive(state,use_llm=False)
    async def write_memory(state):
        try:
            memory=await refresh_memory(user_id)
            memory["date"]=memory["date"].isoformat()
            # Keep graph state JSON serializable, including nested feedback timestamps.
            import json
            return {"memory_summary":json.loads(json.dumps(memory,default=str))}
        except Exception:
            return {"warnings":state.get("warnings",[])+["记忆摘要暂未更新，训练计划仍可查看。"]}
    graph.add_node("exercise_retriever",retrieve_candidates)
    graph.add_node("workout_planner",planner)
    graph.add_node("plan_modifier",adjust_base)
    graph.add_node("rest_day",rest)
    graph.add_node("memory_writer",write_memory)
    graph.add_node("video_retriever",attach_videos)
    graph.set_entry_point("recovery_collector")
    graph.add_edge("recovery_collector","training_history_loader")
    graph.add_edge("training_history_loader","readiness_engine")
    graph.add_conditional_edges("readiness_engine",lambda s: "rest" if s["recovery_level"]=="VERY_LOW" else "train",
                                {"rest":"rest_day","train":"exercise_retriever"})
    graph.add_edge("exercise_retriever","workout_planner")
    graph.add_edge("workout_planner","plan_modifier")
    graph.add_edge("plan_modifier","video_retriever")
    graph.add_edge("rest_day","video_retriever")
    graph.add_edge("video_retriever","memory_writer")
    graph.add_edge("memory_writer",END)
    result=await graph.compile().ainvoke({"user_id":user_id,"user_profile":profiles[0],
        "evaluation_time":datetime.now(timezone.utc).isoformat(),"warnings":[],"messages":[]})
    record={key:value for key,value in result.items() if key != "messages"}
    record.update(workout_id=uuid4().hex,date=datetime.now(timezone.utc))
    await store.save("workout_plans",{"user_id":user_id,"workout_id":record["workout_id"]},record)
    return record
