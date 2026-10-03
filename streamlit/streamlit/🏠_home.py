import streamlit as st


def render_home():
    import streamlit as st
    from utils.api_client import FitnessAPI, init_session_state
    from utils.footer import render_footer
    from utils.sidebar import render_sidebar_disclaimer

    # Configure Streamlit page
    st.set_page_config(
        page_title="智能健身助手",
        page_icon="💪",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state and setup sidebar
    init_session_state()

    # Add disclaimer to sidebar
    render_sidebar_disclaimer()

    st.title("🏋️‍♂️ 智能健身助手")
    st.markdown("### 吃什么、怎么练，为您安排清楚")
    st.write("填写身体情况、健身目标和饮食偏好，获取适合自己的饮食与训练建议。")
    status = FitnessAPI.runtime_status()
    if status.get("database_ready"):
        st.success(f"资料服务已连接，可保存个人资料。食品数据库中有 {status.get('food_count', 0):,} 条记录。")
    else:
        st.warning("资料服务暂不可用，请启动数据库后重试。")
    if not status.get("model_key_configured"):
        st.info("智能服务尚未配置：暂时无法搜索食物或生成计划。请联系维护人员配置模型服务。")
    elif not status.get("vector_index_ready"):
        if status.get("embedding_key_configured") is False:
            st.info("聊天服务已配置。食品检索服务仍需配置，完成后才能搜索食物和生成包含饮食的完整计划。")
        else:
            st.info("食品搜索正在准备中：需要先完成索引建立，再使用搜索和计划生成功能。")
    else:
        st.caption("基础配置已就绪，实际生成还取决于模型服务连接和账户额度。")
    st.subheader("三步开始")
    st.markdown("""
1. **填写个人资料**：输入年龄、身高和体重，选择减脂、增肌或维持体重等目标。
2. **生成完整计划**：选择计划天数，获取每日饮食安排和每周训练方案。
3. **查看并执行**：了解食物份量、训练动作、组数与休息时间，按计划逐步开展。
""")
    st.page_link("pages/1_👤_Profile_Setup.py", label="开始填写个人资料", icon="👤")
    st.page_link("pages/4_😴_Recovery.py", label="记录恢复情况", icon="😴")
    st.page_link("pages/5_🏋️_Today_Workout.py", label="生成今日自适应训练", icon="🏋️")
    st.caption("今日训练可以独立使用，无需等待食品检索配置完成。")
    st.subheader("您可以做什么")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 🥗 饮食安排\n了解每日热量和营养需求，结合饮食偏好选择食物。")
    with col2:
        st.markdown("#### 💪 训练计划\n按每周可训练天数和现有器械安排动作。")
    with col3:
        st.markdown("#### 🔍 食物搜索\n用中文描述需求，例如‘高蛋白早餐’或‘低碳水零食’。")

    # Footer
    render_footer()


st.navigation([
    st.Page(render_home, title="首页", icon="🏠", default=True),
    st.Page("pages/1_👤_Profile_Setup.py", title="个人资料", icon="👤"),
    st.Page("pages/2_📊_Complete_Plan.py", title="完整计划", icon="📊"),
    st.Page("pages/3_🔍_Food_Search.py", title="食物搜索", icon="🔍"),
    st.Page("pages/4_😴_Recovery.py", title="恢复记录", icon="😴"),
    st.Page("pages/5_🏋️_Today_Workout.py", title="今日训练", icon="🏋️"),
    st.Page("pages/6_📈_Training_History.py", title="训练历史", icon="📈"),
    st.Page("pages/7_✅_Workout_Feedback.py", title="训练反馈", icon="✅"),
]).run()
