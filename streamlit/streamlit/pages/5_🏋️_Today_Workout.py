import streamlit as st
from utils.adaptive_ui import setup,call,render_readiness,render_plan,local_time

user=setup("今日训练","🏋️")
st.write("根据恢复记录、近期训练和现有器械安排今天的训练；无需食品向量索引。")
use_model=st.checkbox("使用智能模型选择动作",value=True,help="关闭后使用经过条件筛选的本地动作安排。")
if st.button("生成今日训练",type="primary"):
    with st.spinner("正在评估恢复状态并安排动作……"):
        result=call("POST","/workouts/today/",{"user_id":user,"use_llm":use_model})
    if result:st.session_state.today_workout=result
result=st.session_state.get("today_workout") or call("GET","/workouts/today/"+user,quiet_missing=True)
if result:
    st.caption("计划生成时间（北京时间）："+local_time(result.get("date")))
    render_readiness(result["readiness"])
    for warning in result.get("warnings",[]):st.info(warning)
    render_plan(result["workout_plan"])
    if result.get("base_workout_plan"):
        with st.expander("查看调整前的基础安排"):
            render_plan(result["base_workout_plan"])
    with st.expander("为什么这样调整"):
        for adjustment in result.get("plan_adjustments",[]):
            st.write(adjustment.get("reason",""))
    st.page_link("pages/7_✅_Workout_Feedback.py",label="记录实际训练反馈",icon="✅")
else:st.info("尚未生成训练安排，请先记录恢复情况，再生成今日训练。")
