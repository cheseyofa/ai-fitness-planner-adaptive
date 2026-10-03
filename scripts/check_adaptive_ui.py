"""Exercise the actual Chinese page scripts without live writes/model charges."""
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'streamlit/streamlit'
sys.path.insert(0,str(UI))
from streamlit.testing.v1 import AppTest
from utils.api_client import FitnessAPI
from utils import adaptive_ui

readiness={"score":50,"level":"LOW","recommended_volume_multiplier":.65,"reasons":["数据不足，采用保守安排。"]}
plan={"workout_id":"test-only","date":"2026-10-03T10:00:00+08:00","readiness":readiness,"warnings":[],
      "workout_plan":{"plan_name":"今日训练","weekly_schedule":[{"exercises":[{"exercise_name":"徒手深蹲","target_muscle":"legs","sets":1,"reps":"8–12","rest_seconds":60,"target_rpe":4}]}]}}

def fake(method,path,payload=None,**kwargs):
    if path.startswith('/recovery'):return readiness
    if path.startswith('/workouts/today'):return plan
    if path.startswith('/workouts/history'):return {"sessions":[]}
    if path.startswith('/feedback'):return {"message":"反馈已保存。","warnings":[]}
    return None

with patch.object(FitnessAPI,'get_profile',return_value={"user_id":"user_123"}),patch.object(FitnessAPI,'runtime_status',return_value={}),patch.object(adaptive_ui,'call',side_effect=fake) as api:
    for filename in ['4_😴_Recovery.py','5_🏋️_Today_Workout.py','6_📈_Training_History.py','7_✅_Workout_Feedback.py']:
        page=AppTest.from_file(str(UI/'🏠_home.py'),default_timeout=30).run()
        page.switch_page('pages/'+filename).run()
        assert not page.exception,[x.message for x in page.exception]
        if filename.startswith('4_'):
            next(b for b in page.button if b.label=='保存并评估恢复状态').click().run()
            assert any(c.args[0]=='POST' and c.args[1]=='/recovery/' for c in api.call_args_list)
        elif filename.startswith('5_'):
            next(b for b in page.button if b.label=='生成今日训练').click().run()
        elif filename.startswith('7_'):
            next(b for b in page.button if b.label=='保存训练反馈').click().run()
            sent=[c for c in api.call_args_list if c.args[1]=='/feedback/'][-1].args[2]
            assert sent['completed'] is False and sent['exercises']==[]
        assert not page.exception,[x.message for x in page.exception]
print('PASS: four Chinese adaptive pages, recovery save, plan generation, explicit actual feedback.')
