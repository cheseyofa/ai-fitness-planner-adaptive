import os
import unittest
from copy import deepcopy
from datetime import datetime,timezone
from unittest.mock import patch
os.environ.setdefault("LANGCHAIN_TRACING_V2","false")
from fast_api.app.main import app
from fastapi.testclient import TestClient
from app.services.storage import store


class MemoryStore:
    def __init__(self): self.data={"user_profiles":[{"user_id":"test","workout_duration":20,"equipment_available":["bodyweight"]}]}
    async def find(self,collection,query,limit=200,sort_key="date"):
        def matches(row):
            for key,value in query.items():
                current=row.get(key)
                if isinstance(value,dict):
                    if current is None:return False
                    if "$gt" in value and current<=value["$gt"]:return False
                    if "$lte" in value and current>value["$lte"]:return False
                elif current!=value:return False
            return True
        return deepcopy([r for r in reversed(self.data.get(collection,[])) if matches(r)][:limit])
    async def save(self,collection,query,data):
        rows=self.data.setdefault(collection,[])
        rows[:]=[r for r in rows if not all(r.get(k)==v for k,v in query.items())]
        rows.append(deepcopy(data))


class AdaptiveAPITests(unittest.TestCase):
    def setUp(self):
        self.db=MemoryStore()
        self.patches=[patch.object(store,"find",self.db.find),patch.object(store,"save",self.db.save),
                      patch.dict(os.environ,{"VIDEO_PROVIDER":"mock","EXERCISE_PROVIDER":"local"})]
        for p in self.patches:p.start()
        self.client=TestClient(app)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()

    def test_recovery_api(self):
        r=self.client.post('/v1/recovery/',json={"user_id":"test","subjective_fatigue":9})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()["level"],"VERY_LOW")
        self.assertEqual(self.client.get('/v1/recovery/test').status_code,200)

    def test_no_profile(self):
        self.assertEqual(self.client.post('/v1/workouts/today/',json={"user_id":"unknown","use_llm":False}).status_code,404)

    def test_feedback_history_and_next_plan(self):
        first=self.client.post('/v1/workouts/today/',json={"user_id":"test","use_llm":False})
        self.assertEqual(first.status_code,200,first.text)
        plan=first.json();exercise=plan["workout_plan"]["weekly_schedule"][0]["exercises"][0]
        payload={"user_id":"test","workout_id":plan["workout_id"],"completed":True,
                 "session_rpe":8,"duration_minutes":20,"soreness_after":{"legs":8},
                 "exercises":[{"exercise_name":exercise["exercise_name"],"sets":[{"reps":8,"weight":0}]}]}
        for _ in range(2):self.assertEqual(self.client.post('/v1/feedback/',json=payload).status_code,200)
        self.assertEqual(len(self.client.get('/v1/workouts/history/test').json()["sessions"]),1)
        next_plan=self.client.post('/v1/workouts/today/',json={"user_id":"test","use_llm":False}).json()
        self.assertTrue(all(e["target_muscle"]!="legs" for d in next_plan["workout_plan"].get("weekly_schedule",[]) for e in d["exercises"]))
        self.assertEqual(self.client.get('/v1/memory/test').json()["training"]["completed_sessions"],1)

    def test_cross_user_feedback_rejected(self):
        self.assertEqual(self.client.post('/v1/feedback/',json={"user_id":"other","workout_id":"x","completed":False}).status_code,404)

    def test_very_low_skips_planner(self):
        self.client.post('/v1/recovery/',json={"user_id":"test","subjective_fatigue":9})
        r=self.client.post('/v1/workouts/today/',json={"user_id":"test","use_llm":False})
        self.assertTrue(r.json()["workout_plan"]["rest_day"])
