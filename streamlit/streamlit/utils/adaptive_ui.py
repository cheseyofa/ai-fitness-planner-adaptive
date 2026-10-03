import requests
import streamlit as st
from datetime import datetime,timezone,timedelta
from .api_client import FitnessAPI,init_session_state

LEVELS={"HIGH":"良好","MEDIUM":"中等","LOW":"偏低","VERY_LOW":"很低"}
MUSCLES={"legs":"腿部","chest":"胸部","back":"背部","core":"核心","arms":"手臂","shoulders":"肩部"}


def local_time(value) -> str:
    try:
        parsed=datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone(timedelta(hours=8))).strftime("%Y年%m月%d日 %H:%M")
    except (ValueError,TypeError):return "时间未记录"


def setup(title: str,icon: str) -> str:
    st.set_page_config(page_title=title+" - 智能健身助手",page_icon=icon,layout="wide")
    init_session_state()
    from .sidebar import render_sidebar_disclaimer
    render_sidebar_disclaimer()
    st.header(icon+" "+title)
    return st.session_state.user_id


def call(method: str,path: str,payload: dict | None=None,*,quiet_missing: bool=False):
    try:
        response=requests.request(method,FitnessAPI.get_api_url()+"/v1"+path,json=payload,timeout=120)
        if response.status_code==404 and quiet_missing:return None
        if response.status_code==404:
            st.warning("尚未找到相关资料或训练计划，请先创建个人资料并生成计划。")
            return None
        if response.status_code==422:
            st.error("填写内容不符合要求，请检查时间、数值范围和必填信息。")
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        st.error("暂时无法完成操作，请确认本地服务运行正常后重试。")
        return None


def render_readiness(result: dict) -> None:
    a,b,c=st.columns(3)
    a.metric("恢复评分",f"{result.get('score',0):.2f} 分")
    b.metric("恢复状态",LEVELS.get(result.get("level"),"待评估"))
    c.metric("建议训练量",f"{result.get('recommended_volume_multiplier',1):.0%}")
    st.caption("评分来自固定计算规则，仅用于训练安排参考。缺失数据会采用保守策略。")
    for reason in result.get("reasons",[]):st.write("• "+reason)


def render_plan(plan: dict) -> None:
    st.subheader(plan.get("plan_name","训练安排"))
    if plan.get("rest_day"):
        st.info(plan.get("adjustment_summary","今天以休息为主。"))
    for day in plan.get("weekly_schedule",[]):
        for e in day.get("exercises",[]):
            with st.container(border=True):
                st.markdown("**"+e["exercise_name"]+"**")
                st.write(f"{e['sets']} 组 · 每组 {e['reps']} 次 · 组间休息 {e['rest_seconds']} 秒")
                st.write(f"目标用力程度：{e.get('target_rpe',6):g}/10；部位：{MUSCLES.get(e.get('target_muscle'),'其他')}")
                st.caption(e.get("notes",""))
                for video in e.get("videos",[]):
                    st.link_button("观看动作教学",video["url"])
    if plan.get("adjustment_summary"):st.write(plan["adjustment_summary"])
