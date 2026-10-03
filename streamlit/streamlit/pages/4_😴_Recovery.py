import streamlit as st
from utils.adaptive_ui import setup,call,render_readiness,MUSCLES
from utils.api_client import FitnessAPI

user=setup("恢复记录","😴")
profile=FitnessAPI.get_profile(user)
if not profile:
    st.info("请先在个人资料页保存资料。")
    st.stop()
st.write("记录昨晚睡眠及当前感受。不清楚的项目可以不填，不会按恢复良好处理。")
with st.expander("个人恢复基准与训练限制"):
    with st.form("baselines"):
        normal=st.number_input("通常睡眠时长（小时）",min_value=1.0,max_value=24.0,value=float(profile.get("normal_sleep_duration",8)))
        baseline_hrv=st.number_input("平时心率变异性（毫秒，填 0 表示未知）",min_value=0.0,value=float(profile.get("baseline_hrv") or 0))
        baseline_hr=st.number_input("平时静息心率（次/分钟，填 0 表示未知）",min_value=0.0,value=float(profile.get("baseline_resting_hr") or 0))
        injuries=st.multiselect("已有伤痛部位",["膝部","腰背部","肩部","手腕","手肘","髋部","脚踝","不明疼痛"],default=[x for x in profile.get("injuries",[]) if x in ["膝部","腰背部","肩部","手腕","手肘","髋部","脚踝","不明疼痛"]])
        complete=st.checkbox("我已完整记录最近七天的所有训练",value=profile.get("history_complete",False))
        if st.form_submit_button("保存基准与限制"):
            payload={**profile,"normal_sleep_duration":normal,"baseline_hrv":baseline_hrv or None,"baseline_resting_hr":baseline_hr or None,"injuries":injuries,"history_complete":complete}
            if FitnessAPI.create_profile(payload):st.success("已保存。")
with st.form("recovery"):
    sleep_known=st.checkbox("填写昨晚睡眠",value=True)
    hours=st.number_input("睡眠时长（小时）",min_value=0.0,max_value=24.0,value=8.0,step=.5)
    score_known=st.checkbox("我有设备记录的睡眠评分")
    score=st.slider("睡眠评分",0,100,80)
    hrv_known=st.checkbox("填写今天的心率变异性")
    hrv=st.number_input("心率变异性（毫秒）",min_value=1.0,value=50.0)
    hr_known=st.checkbox("填写今天的静息心率")
    hr=st.number_input("静息心率（次/分钟）",min_value=1.0,value=60.0)
    fatigue=st.slider("当前疲劳程度（0 为不疲劳，10 为非常疲劳）",0,10,3)
    soreness={key:st.slider(label+"酸痛程度",0,10,0,key="sore_"+key) for key,label in MUSCLES.items()}
    if st.form_submit_button("保存并评估恢复状态"):
        payload={"user_id":user,"subjective_fatigue":fatigue,"soreness":soreness}
        if sleep_known:payload["sleep"]={"sleep_duration_hours":hours,"sleep_score":score if score_known else None}
        if hrv_known:payload["hrv"]={"hrv_ms":hrv}
        if hr_known:payload["resting_hr"]=hr
        result=call("POST","/recovery/",payload)
        if result:st.session_state.recovery_result=result;st.success("恢复记录已保存。")
result=st.session_state.get("recovery_result") or call("GET","/recovery/"+user,quiet_missing=True)
if result:render_readiness(result)
