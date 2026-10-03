from ..runtime import require_openai_key, CHINESE_OUTPUT
import os
import json
import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from pymongo import MongoClient

# LangSmith integration
from langsmith import traceable

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from ..model_provider import create_chat_model
from ..services.recovery_context import collect_recovery, load_history, compute_readiness

# Import existing agent classes
from .agents import (
    ProfileManagerAgent,
    MealPlannerAgent,
    WorkoutPlannerAgent,
    PlanSummaryAgent,
    UserProfile,
    MealPlanRequest,
    WorkoutPlanRequest,
    get_mongo_client,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("langgraph_fitness_agents")

langgraph_agents = APIRouter()


# LangGraph State Definition
class FitnessState(TypedDict):
    """State for the fitness planning workflow"""

    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    user_profile: Optional[Dict[str, Any]]
    meal_plan: Optional[Dict[str, Any]]
    workout_plan: Optional[Dict[str, Any]]
    summary: Optional[str]
    current_step: str
    errors: List[str]
    preferences: Dict[str, Any]
    evaluation_time: str
    recovery_input: Dict[str, Any]
    sleep_data: Optional[Dict[str, Any]]
    hrv_data: Optional[Dict[str, Any]]
    resting_hr_data: Optional[Dict[str, Any]]
    soreness_data: Dict[str, float]
    subjective_fatigue: Optional[float]
    training_history: List[Dict[str, Any]]
    training_load_result: Dict[str, Any]
    recent_training_load: Optional[float]
    readiness: Dict[str, Any]
    readiness_score: Optional[float]
    recovery_level: Optional[str]
    recovery_reasons: List[str]
    base_workout_plan: Optional[Dict[str, Any]]
    plan_adjustments: List[Dict[str, Any]]
    exercise_candidates: List[Dict[str, Any]]
    exercise_videos: List[Dict[str, Any]]
    workout_feedback: Optional[Dict[str, Any]]
    memory_summary: Optional[Dict[str, Any]]
    warnings: List[str]
    tool_traces: List[Dict[str, Any]]


# Pydantic models for API
class LangGraphFitnessRequest(BaseModel):
    user_id: str
    user_profile: Optional[UserProfile] = None
    meal_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    workout_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    generate_meal_plan: bool = True
    generate_workout_plan: bool = True
    use_o3_mini: bool = True
    use_full_database: bool = False


class LangGraphFitnessResponse(BaseModel):
    user_id: str
    workflow_status: str
    user_profile: Optional[Dict[str, Any]] = None
    meal_plan: Optional[Dict[str, Any]] = None
    workout_plan: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    execution_steps: List[str] = []
    errors: List[str] = []
    generated_at: datetime
    readiness_score: Optional[float] = None
    recovery_level: Optional[str] = None
    recovery_reasons: List[str] = Field(default_factory=list)
    readiness: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    base_workout_plan: Optional[Dict[str, Any]] = None
    plan_adjustments: List[Dict[str, Any]] = Field(default_factory=list)


class FitnessWorkflow:
    """LangGraph workflow orchestrator for fitness planning"""

    def __init__(self, use_o3_mini: bool = True, use_full_database: bool = False):
        self.profile_agent = ProfileManagerAgent()
        self.meal_agent = MealPlannerAgent(use_o3_mini=use_o3_mini, use_full_database=use_full_database)
        self.workout_agent = WorkoutPlannerAgent()
        self.summary_agent = PlanSummaryAgent()
        self.use_o3_mini = use_o3_mini
        self.use_full_database = use_full_database

        # Initialize LLM for coordination
        self.coordinator_llm = create_chat_model(temperature=0.3)

        # Build the workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""

        workflow = StateGraph(FitnessState)

        # Add nodes for each step
        workflow.add_node("profile_manager", self._manage_profile)
        workflow.add_node("meal_planner", self._plan_meals)
        workflow.add_node("workout_planner", self._plan_workout)
        workflow.add_node("plan_coordinator", self._coordinate_plans)
        workflow.add_node("summary_generator", self._generate_summary)

        workflow.add_node("recovery_collector", collect_recovery)
        workflow.add_node("training_history_loader", load_history)
        workflow.add_node("readiness_engine", compute_readiness)
        workflow.add_edge("profile_manager", "recovery_collector")
        workflow.add_edge("recovery_collector", "training_history_loader")
        workflow.add_edge("training_history_loader", "readiness_engine")
        # Define the workflow edges
        workflow.set_entry_point("profile_manager")

        # Conditional routing based on preferences
        workflow.add_conditional_edges(
            "readiness_engine",
            self._route_after_profile,
            {
                "meal_only": "meal_planner",
                "workout_only": "workout_planner",
                "both": "plan_coordinator",
                "error": END,
            },
        )

        workflow.add_edge("plan_coordinator", "meal_planner")
        workflow.add_edge("meal_planner", "workout_planner")
        workflow.add_edge("workout_planner", "summary_generator")
        workflow.add_edge("summary_generator", END)

        return workflow.compile()

    @traceable(name="manage_profile")
    async def _manage_profile(self, state: FitnessState) -> FitnessState:
        """Node: Manage user profile and calculate nutritional needs"""
        logger.info(f"Managing profile for user: {state['user_id']}")

        try:
            state["current_step"] = "profile_management"

            # Get or create user profile
            client = get_mongo_client()
            db = client[os.getenv("MONGO_DB_NAME", "usda_nutrition")]
            profiles = db["user_profiles"]

            existing_profile = profiles.find_one({"user_id": state["user_id"]})

            if existing_profile:
                existing_profile.pop("_id", None)
                profile = UserProfile(**existing_profile)
                logger.info("Loaded existing user profile")
            else:
                # Create new profile with defaults
                profile = UserProfile(
                    user_id=state["user_id"],
                    age=30,
                    weight=70.0,
                    height=175.0,
                    activity_level="moderate",
                    fitness_goal="maintenance",
                )
                logger.info("Created new user profile with defaults")

            # Update profile with calculated values
            updated_profile = await self.profile_agent.update_profile(profile)

            state["user_profile"] = updated_profile.dict()
            state["messages"].append(
                SystemMessage(
                    content=f"个人资料已更新，每日目标热量：{updated_profile.target_calories} 千卡"
                )
            )

            client.close()

        except Exception as e:
            logger.exception("Profile management failed")
            error_msg = "个人资料处理未完成，请检查服务配置后重试。"
            logger.error(error_msg)
            state["errors"].append(error_msg)

        return state

    def _route_after_profile(self, state: FitnessState) -> str:
        """Conditional routing after profile management"""
        if state["errors"]:
            return "error"

        preferences = state.get("preferences", {})
        generate_meal = preferences.get("generate_meal_plan", True)
        generate_workout = preferences.get("generate_workout_plan", True)

        if generate_meal and generate_workout:
            return "both"
        elif generate_meal:
            return "meal_only"
        elif generate_workout:
            return "workout_only"
        else:
            return "both"  # Default to both if unclear

    @traceable(name="plan_meals")
    async def _plan_meals(self, state: FitnessState) -> FitnessState:
        """Node: Generate meal plan"""
        logger.info(f"Planning meals for user: {state['user_id']}")

        try:
            state["current_step"] = "meal_planning"

            if not state.get("user_profile"):
                raise ValueError("User profile not available for meal planning")

            profile = UserProfile(**state["user_profile"])

            # Create meal plan request
            meal_preferences = state.get("preferences", {}).get("meal_preferences", {})
            days = meal_preferences.get("days", 7)
            request = MealPlanRequest(
                user_id=state["user_id"],
                meal_count=meal_preferences.get("meal_count", 3),
                days=days,
            )

            meal_plan = await self.meal_agent.generate_meal_plan(profile, request)
            if meal_plan.get("error"):
                raise RuntimeError("饮食计划生成失败，请稍后重试。")
            state["meal_plan"] = meal_plan

            state["messages"].append(
                SystemMessage(content=f"已生成 {days} 天饮食计划")
            )

        except Exception as e:
            logger.exception("Meal planning failed")
            error_msg = "饮食计划未完成，请检查服务配置后重试。"
            logger.error(error_msg)
            state["errors"].append(error_msg)

        return state

    @traceable(name="plan_workout")
    async def _plan_workout(self, state: FitnessState) -> FitnessState:
        """Node: Generate workout plan"""
        if not state.get("preferences", {}).get("generate_workout_plan", True):
            return state
        logger.info(f"Planning workouts for user: {state['user_id']}")

        from ..services.adaptive_planning import plan_adaptive
        state.update(await plan_adaptive(state))
        state["messages"].append(SystemMessage(content="已根据恢复状态和动作清单生成今日训练安排"))

        return state

    async def _coordinate_plans(self, state: FitnessState) -> FitnessState:
        """Node: Coordinate between meal and workout planning"""
        logger.info(f"Coordinating plans for user: {state['user_id']}")

        try:
            state["current_step"] = "plan_coordination"

            # Use LLM to coordinate timing and interactions between plans
            coordination_prompt = f"""
            You are coordinating meal and workout plans for optimal results.
            
            User Goal: {state.get('user_profile', {}).get('fitness_goal', 'maintenance')}
            
            Consider:
            - Pre/post workout nutrition timing
            - Rest day meal adjustments
            - Macro distribution around training
            - Recovery nutrition needs
            
            Provide coordination insights as a brief message.
            """

            coordination_message = await self.coordinator_llm.ainvoke(
                [SystemMessage(content=CHINESE_OUTPUT + coordination_prompt)]
            )

            state["messages"].append(
                SystemMessage(
                    content=f"饮食与训练协调建议： {coordination_message.content}"
                )
            )

        except Exception as e:
            logger.exception("Plan coordination failed")
            error_msg = "计划协调未完成，请检查服务配置后重试。"
            logger.error(error_msg)
            state["errors"].append(error_msg)

        return state

    async def _generate_summary(self, state: FitnessState) -> FitnessState:
        """Node: Generate comprehensive summary"""
        logger.info(f"Generating summary for user: {state['user_id']}")

        try:
            state["current_step"] = "summary_generation"

            if not state.get("user_profile"):
                raise ValueError("User profile not available for summary")

            profile = UserProfile(**state["user_profile"])
            meal_plan = state.get("meal_plan") or {}
            workout_plan = state.get("workout_plan") or {}

            summary = await self.summary_agent.create_summary(
                profile, meal_plan, workout_plan
            )

            state["summary"] = summary
            state["messages"].append(
                SystemMessage(content="完整健身计划总结已生成")
            )

        except Exception as e:
            logger.exception("Summary generation failed")
            error_msg = "总结生成未完成，请检查服务配置后重试。"
            logger.error(error_msg)
            state["errors"].append(error_msg)

        return state

    @traceable(name="execute_fitness_workflow")
    async def execute_workflow(
        self, request: LangGraphFitnessRequest
    ) -> Dict[str, Any]:
        """Execute the complete fitness planning workflow"""

        # Initialize state
        initial_state: FitnessState = {
            "messages": [
                HumanMessage(
                    content=f"Generate fitness plan for user {request.user_id}"
                )
            ],
            "evaluation_time": datetime.now(timezone.utc).isoformat(),
            "warnings": [],
            "user_id": request.user_id,
            "user_profile": None,
            "meal_plan": None,
            "workout_plan": None,
            "summary": None,
            "current_step": "initialization",
            "errors": [],
            "preferences": {
                "generate_meal_plan": request.generate_meal_plan,
                "generate_workout_plan": request.generate_workout_plan,
                "meal_preferences": request.meal_preferences,
                "workout_preferences": request.workout_preferences,
            },
        }

        # If user profile provided, update it first
        if request.user_profile:
            request.user_profile.user_id = request.user_id
            await self.profile_agent.update_profile(request.user_profile)

        # Execute workflow
        try:
            final_state = await self.workflow.ainvoke(initial_state)

            # Track execution steps
            execution_steps = [
                msg.content
                for msg in final_state["messages"]
                if isinstance(msg, SystemMessage)
            ]

            return {
                "user_id": request.user_id,
                "workflow_status": (
                    "completed"
                    if not final_state["errors"]
                    else "completed_with_errors"
                ),
                "user_profile": final_state.get("user_profile"),
                "meal_plan": final_state.get("meal_plan"),
                "workout_plan": final_state.get("workout_plan"),
                "summary": final_state.get("summary"),
                "execution_steps": execution_steps,
                **{key: final_state.get(key) for key in ("readiness_score", "recovery_level", "recovery_reasons", "readiness", "warnings", "base_workout_plan", "plan_adjustments")},
                "errors": final_state.get("errors", []),
                "generated_at": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Workflow execution error: {str(e)}")
            return {
                "user_id": request.user_id,
                "workflow_status": "failed",
                "errors": ["计划生成未完成，请检查服务配置后重试。"],
                "generated_at": datetime.now(),
            }


# Initialize workflow - will be dynamically created per request
fitness_workflow = None


# API Endpoints
@langgraph_agents.post(
    "/generate-fitness-plan/", response_model=LangGraphFitnessResponse
)
async def generate_fitness_plan_workflow(request: LangGraphFitnessRequest):
    """Generate complete fitness plan using LangGraph workflow orchestration"""
    require_openai_key()
    try:
        # Create workflow instance with the requested model and database preferences
        workflow = FitnessWorkflow(use_o3_mini=request.use_o3_mini, use_full_database=request.use_full_database)
        result = await workflow.execute_workflow(request)
        return LangGraphFitnessResponse(**result)

    except Exception as e:
        logger.error(f"Error in fitness plan workflow: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to execute fitness plan workflow: {str(e)}"
        )








