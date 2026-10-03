import asyncio
import json
import sys
import time
import os
from unittest.mock import patch,AsyncMock
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from evaluation.test_cases import CASES,evaluate_case,NOW
from fast_api.app.services.adaptive_planning import plan_adaptive
from fast_api.app.services.exercise_provider import LocalExerciseProvider,CATALOG
from fast_api.app.services.remote_exercises import WgerMCPProvider,WgerExerciseProvider
from fast_api.app.tools.exercise_tools import retrieve_exercises


async def main():
    durations=[];correct=0;constraint_pass=0
    for hours,fatigue,expected in CASES:
        started=time.perf_counter();r=evaluate_case(hours,fatigue)
        correct+=r.level==expected
        state=await plan_adaptive({'readiness':r.model_dump(),'user_profile':{},'evaluation_time':NOW.isoformat(),'training_history':[]},use_llm=False)
        plan=state['workout_plan']
        allowed={e['id'] for e in CATALOG}
        constraint_pass+=all(e['exercise_id'] in allowed and 1<=e['sets']<=3 and 1<=e['target_rpe']<=8
                             for d in plan.get('weekly_schedule',[]) for e in d['exercises']) and (r.level!='VERY_LOW' or plan.get('rest_day',False))
        durations.append((time.perf_counter()-started)*1000)
    relevant={'squat','bridge','calf'}
    hits=await LocalExerciseProvider().search_exercises(target_muscle='legs',equipment=['bodyweight'],limit=10)
    trace_rows=[];fallback_pass=0
    with patch.dict(os.environ,{'EXERCISE_PROVIDER':'mcp'}),patch.object(WgerMCPProvider,'search_exercises',AsyncMock(side_effect=RuntimeError())),patch.object(WgerExerciseProvider,'search_exercises',AsyncMock(side_effect=RuntimeError())):
        for _ in range(3):
            rows,traces=await retrieve_exercises({});trace_rows.extend(traces);fallback_pass+=bool(rows)
    live_path=ROOT/'docs/adaptive_live_verification.json'
    live=json.loads(live_path.read_text(encoding='utf-8')) if live_path.exists() else {}
    metrics=(live.get('first_plan',{}).get('base_workout_plan') or {}).get('generation_metrics',{})
    report={'scope':'24 synthetic offline cases; 3 injected failures; separately labeled one live model sample; not medical efficacy',
        'cases':len(CASES),'readiness_classification_accuracy':correct/len(CASES),
        'plan_constraint_pass_rate':constraint_pass/len(CASES),
        'exercise_retrieval_recall_at_10':len(relevant & {e['id'] for e in hits})/len(relevant),
        'average_agent_latency_ms':sum(durations)/len(durations),
        'tool_call_success_rate':sum(t['status']=='success' for t in trace_rows)/len(trace_rows),
        'tool_rate_scope':'9 attempts: 6 deliberate remote failures, 3 local successes; not external availability',
        'structured_output_valid_rate':float(metrics['structured_output_valid']) if metrics.get('structured_output_valid') is not None else None,
        'fallback_success_rate':fallback_pass/3,
        'average_token_usage':metrics.get('total_tokens'),
        'live_model_samples':1 if metrics.get('model_called') else 0}
    (ROOT/'docs/adaptive_benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':asyncio.run(main())
