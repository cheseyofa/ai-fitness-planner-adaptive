import streamlit as st
from utils.adaptive_ui import setup,call,local_time

user=setup("训练历史","📈")
result=call("GET","/workouts/history/"+user)
if result:
    rows=[{"训练时间（北京时间）":local_time(s.get("date")),"完成状态":"已完成" if s.get("completed") else "未完成",
           "实际时长（分钟）":s.get("duration_minutes"),"用力程度":s.get("session_rpe"),
           "已记录动作数":len(s.get("exercises",[]))} for s in result["sessions"]]
    if rows:st.dataframe(rows,use_container_width=True,hide_index=True)
    else:st.info("暂无训练记录。完成今日训练后，请在训练反馈页记录实际情况。")
if st.button("查看训练记忆摘要"):
    memory=call("GET","/memory/"+user)
    if memory:
        st.metric("近期已完成训练",memory["training"]["completed_sessions"])
        st.write("近期记录的动作："+"、".join(memory["training"]["recent_exercise_names"]))
