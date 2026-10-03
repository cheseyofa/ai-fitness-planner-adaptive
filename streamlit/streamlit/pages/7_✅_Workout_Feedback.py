import streamlit as st
from utils.adaptive_ui import setup,call,MUSCLES

user=setup("训练反馈","✅")
plan=st.session_state.get("today_workout") or call("GET","/workouts/today/"+user,quiet_missing=True)
if not plan:
    st.info("请先生成今日训练安排。")
    st.stop()
st.write("只填写实际完成的内容。重复提交同一计划会更新记录，不会重复累计负荷。")
with st.form("feedback"):
    completed=st.checkbox("我已完成本次训练",value=False)
    minutes=st.number_input("实际训练时长（分钟）",min_value=1,max_value=600,value=20)
    rpe=st.slider("实际用力程度（0 为无负担，10 为极限）",0,10,5)
    difficulty=st.slider("整体困难程度",0,10,5)
    actual=[]
    for day in plan["workout_plan"].get("weekly_schedule",[]):
        for index,e in enumerate(day.get("exercises",[])):
            st.markdown("**"+e["exercise_name"]+"**")
            count=st.number_input("实际完成组数",min_value=0,max_value=20,value=0,key="sets_"+str(index))
            reps=st.number_input("每组实际次数（当前按相同次数记录）",min_value=0,max_value=100,value=0,key="reps_"+str(index))
            weight=st.number_input("每组外加重量（千克，自重填 0）",min_value=0.0,max_value=500.0,value=0.0,key="weight_"+str(index))
            if count and reps:actual.append({"exercise_name":e["exercise_name"],"sets":[{"reps":reps,"weight":weight,"rpe":rpe} for _ in range(count)]})
    soreness={key:st.slider(label+"训练后酸痛",0,10,0,key="after_"+key) for key,label in MUSCLES.items()}
    notes=st.text_area("补充感受（可选）")
    if st.form_submit_button("保存训练反馈"):
        if plan["workout_plan"].get("rest_day") and completed:
            st.warning("这是一份休息安排，请不要将休息记录为完成训练。")
        else:
            result=call("POST","/feedback/",{"user_id":user,"workout_id":plan["workout_id"],"completed":completed,
                        "duration_minutes":minutes if completed else None,"session_rpe":rpe if completed else None,
                        "perceived_difficulty":difficulty,"exercises":actual,"soreness_after":soreness,"notes":notes})
            if result:
                st.success(result["message"])
                for warning in result.get("warnings",[]):st.info(warning)
