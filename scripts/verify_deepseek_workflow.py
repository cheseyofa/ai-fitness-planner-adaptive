"""Explicit live verification: one synthetic profile, workout-only graph, then cleanup."""
import json
import os
import sys
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env", override=True)
    base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    http = requests.Session()
    http.trust_env = False
    health = http.get(base + "/health", timeout=15).json()
    print("服务状态：", health, flush=True)
    assert health["chat_provider"] == "deepseek" and health["model_key_configured"]
    user_id = "deepseek-check-" + uuid.uuid4().hex
    mongo = MongoClient(os.getenv("MONGO_HOST", "localhost"), int(os.getenv("MONGO_PORT", "27019")),
                        username=os.getenv("MONGO_USER"), password=os.getenv("MONGO_PASSWORD"), authSource="admin")
    collection = mongo[os.getenv("MONGO_DB_NAME", "usda_nutrition")].user_profiles
    try:
        profile = dict(user_id=user_id, age=30, weight=70, height=175, fitness_goal="maintenance",
                       activity_level="moderate", workout_frequency=1, workout_duration=20,
                       equipment_available=["bodyweight"])
        response = http.post(base + "/v1/agents/profile/", json=profile, timeout=20)
        response.raise_for_status()
        response = http.post(base + "/v1/langgraph/generate-fitness-plan/", json=dict(
            user_id=user_id, generate_meal_plan=False, generate_workout_plan=True,
            use_o3_mini=False, workout_preferences={"days_per_week":1,"duration_minutes":20}), timeout=420)
        print("训练流程状态码：", response.status_code, flush=True)
        response.raise_for_status()
        result = response.json()
        assert result["workflow_status"] == "completed", result.get("errors")
        assert result["workout_plan"] and result["summary"] and not result.get("errors")
        (ROOT / "docs/deepseek_workout_demo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print("通过：真实资料读取、训练计划、中文总结；样例结果已保存。", flush=True)
    finally:
        collection.delete_one({"user_id":user_id})
        mongo.close()
        print("已清理本次临时资料。",flush=True)


if __name__ == "__main__":
    main()
