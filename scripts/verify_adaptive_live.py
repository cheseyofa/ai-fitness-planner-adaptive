"""Real local Mongo/API loop; synthetic user only, one bounded live model call."""
import json
import os
import sys
import time
import uuid
from pathlib import Path
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(ROOT/'.env',override=True)
http=requests.Session();http.trust_env=False
base='http://localhost:8000'
for attempt in range(30):
    try:
        http.get(base+'/health',timeout=3).raise_for_status();break
    except requests.RequestException:
        if attempt==29:raise
        time.sleep(1)
uid='adaptive-check-'+uuid.uuid4().hex
mongo=MongoClient(os.getenv('MONGO_HOST','localhost'),int(os.getenv('MONGO_PORT','27019')),
                  username=os.getenv('MONGO_USER'),password=os.getenv('MONGO_PASSWORD'),authSource='admin')
db=mongo[os.getenv('MONGO_DB_NAME','usda_nutrition')]
def call(method,path,data=None):
    r=http.request(method,base+'/v1'+path,json=data,timeout=120)
    if r.status_code>=400:raise RuntimeError(f'{path}: HTTP {r.status_code}')
    return r.json()
try:
    call('POST','/agents/profile/',dict(user_id=uid,age=30,weight=70,height=175,activity_level='moderate',
        fitness_goal='maintenance',equipment_available=['bodyweight'],workout_duration=20,workout_frequency=3))
    recovery=call('POST','/recovery/',{'user_id':uid,'sleep':{'sleep_duration_hours':8},
        'hrv':{'hrv_ms':50,'baseline_hrv_ms':50},'resting_hr':60,'baseline_resting_hr':60,
        'subjective_fatigue':2,'soreness':{'legs':0}})
    print('真实恢复评分：',recovery['score'],flush=True)
    first=call('POST','/workouts/today/',{'user_id':uid,'use_llm':True})
    assert first['workout_plan']['weekly_schedule']
    selected=first['workout_plan']['weekly_schedule'][0]['exercises'][0]
    payload={'user_id':uid,'workout_id':first['workout_id'],'completed':True,'session_rpe':8,'duration_minutes':20,
        'soreness_after':{'legs':8},'exercises':[{'exercise_name':selected['exercise_name'],'sets':[{'weight':0,'reps':8}]}]}
    call('POST','/feedback/',payload);call('POST','/feedback/',payload)
    history=call('GET','/workouts/history/'+uid)
    assert len(history['sessions'])==1
    second=call('POST','/workouts/today/',{'user_id':uid,'use_llm':False})
    assert all(e['target_muscle']!='legs' for d in second['workout_plan'].get('weekly_schedule',[]) for e in d['exercises'])
    assert call('GET','/memory/'+uid)['training']['completed_sessions']==1
    call('POST','/recovery/',{'user_id':uid,'subjective_fatigue':9})
    rest=call('POST','/workouts/today/',{'user_id':uid,'use_llm':False})
    assert rest['workout_plan']['rest_day']
    report={'profile_recovery_plan_feedback_history_memory':'PASS','duplicate_feedback':'PASS',
        'soreness_changes_next_plan':'PASS','very_low_rest':'PASS',
        'live_model_fallback_used':any('智能动作选择暂不可用' in x for x in first.get('warnings',[])),
        'first_plan':first,'next_plan':second,'rest_plan':rest}
    (ROOT/'docs/adaptive_live_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS：真实资料、恢复、计划、反馈、历史、记忆、重新规划；重复提交只保留一条训练记录。',flush=True)
finally:
    for collection in ('user_profiles','recovery_records','workout_plans','workout_sessions','workout_feedback','user_memory'):
        db[collection].delete_many({'user_id':uid})
    mongo.close()
    print('已清理本次虚构测试用户的全部记录。',flush=True)
