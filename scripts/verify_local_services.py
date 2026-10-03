"""Verify actual local persistence without touching existing user profiles or AI."""
from pathlib import Path
import os
import time
import uuid
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
base = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
session = requests.Session()
session.trust_env = False
for attempt in range(45):
    try:
        status = session.get(base + "/health", timeout=4)
        status.raise_for_status()
        break
    except requests.RequestException:
        if attempt == 44:
            raise
        time.sleep(1)
print("Runtime status:", status.json())
assert status.json()["database_ready"]
assert status.json()["food_count"] == 5000

uid = "environment-check-" + uuid.uuid4().hex
profile = {"user_id": uid, "age": 35, "weight": 70, "height": 175,
           "activity_level": "moderate", "fitness_goal": "maintenance",
           "workout_frequency": 3, "equipment_available": ["bodyweight"]}
client = MongoClient(os.getenv("MONGO_HOST", "localhost"), int(os.getenv("MONGO_PORT", "27019")),
                     username=os.getenv("MONGO_USER"), password=os.getenv("MONGO_PASSWORD"), authSource="admin")
collection = client[os.getenv("MONGO_DB_NAME", "usda_nutrition")].user_profiles
try:
    response = session.post(base + "/v1/agents/profile/", json=profile, timeout=15)
    response.raise_for_status()
    assert response.json()["target_calories"] > 0
    assert collection.find_one({"user_id": uid}) is not None
    response = session.get(base + f"/v1/agents/profile/{uid}", timeout=15)
    response.raise_for_status()
    assert response.json()["weight"] == 70
    profile["weight"] = 72
    session.post(base + "/v1/agents/profile/", json=profile, timeout=15).raise_for_status()
    assert session.get(base + f"/v1/agents/profile/{uid}", timeout=15).json()["weight"] == 72
    assert collection.count_documents({"user_id": uid}) == 1
    print("PASS: real MongoDB profile create/read/update; no duplicate records")
finally:
    collection.delete_one({"user_id": uid})
    client.close()
assert session.get(base + f"/v1/agents/profile/{uid}", timeout=15).status_code == 404
response = session.get(base + "/v1/nutrition_setup/database_availability/", timeout=15)
response.raise_for_status()
assert response.json()["sample_database"]["document_count"] == 5000
session.get(base + "/openapi.json", timeout=10).raise_for_status()
session.get("http://localhost:8501/_stcore/health", timeout=10).raise_for_status()
print("PASS: sample data count, missing-profile 404, backend routes and frontend health")
