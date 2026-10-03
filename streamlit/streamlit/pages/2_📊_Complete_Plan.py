import streamlit as st
from utils.api_client import FitnessAPI, init_session_state
from utils.footer import render_footer
from utils.sidebar import render_sidebar_disclaimer

# Configure page
st.set_page_config(
    page_title="完整计划 - 智能健身助手", page_icon="📊", layout="wide"
)

# Initialize session state and setup sidebar
init_session_state()

# Add disclaimer to sidebar
render_sidebar_disclaimer()

# Add meal plan days selector in sidebar
with st.sidebar:
    st.subheader("🍽️ 饮食计划设置")
    meal_plan_days = st.selectbox(
        "饮食计划天数",
        options=[1, 2, 3, 4, 5, 6, 7],
        index=0,  # Default to 1 day
        help="选择需要生成的饮食计划天数，天数越少，生成越快。",
    )

st.header("📊 完整健身计划")

if not st.session_state.get("current_profile") and not FitnessAPI.get_profile(
    st.session_state.user_id
):
    st.warning("⚠️ 请先创建个人资料！")
    if st.button("👤 前往个人资料"):
        st.switch_page("pages/1_👤_Profile_Setup.py")
    st.stop()

st.markdown(
    "根据您的个人资料生成完整健身计划，包含饮食安排和训练方案。"
)

# Plan configuration
col1, col2 = st.columns(2)

with col1:
    st.subheader("🍽️ 饮食计划设置")
    st.info(
        f"将生成 {meal_plan_days} 天的饮食计划"
    )

with col2:
    st.subheader("💪 训练设置")

    # Get current profile to display workout frequency
    current_profile = st.session_state.get("current_profile") or FitnessAPI.get_profile(
        st.session_state.user_id
    )
    if current_profile and current_profile.get("workout_frequency"):
        workout_freq = current_profile["workout_frequency"]
        st.info(f"训练频率：每周 {workout_freq} 天")
    else:
        st.info("请在个人资料中设置每周训练天数")

# AI 模型设置
st.sidebar.subheader("🤖 规划方式")
use_o3_mini = st.sidebar.checkbox(
    "深入规划（耗时较长）", value=True,
    help="使用已配置的高级模型；当前服务为深度求索时，使用其高级规划模型。"
)

# with col2:
#     use_full_database = st.checkbox(
#         "Use full USDA database",
#         value=False,
#         help="Use the complete USDA database vs the sample dataset. Requires full database to be imported.",
#     )
use_full_database = False
# Database availability check
if use_full_database:
    # Check if full database is available
    try:
        db_status = FitnessAPI.check_database_availability()
        if not db_status.get("full_database", {}).get("available", False):
            st.error(
                "❌ 完整 USDA 数据库不可用，目前仅提供样本数据。"
                "请先导入完整数据库，或关闭完整数据库选项。"
            )
            use_full_database = False  # Override to use sample
    except Exception as e:
        st.warning(f"⚠️ 无法检查数据库状态： {str(e)}")
        use_full_database = False

# Generate button
runtime = FitnessAPI.runtime_status()
if not runtime.get("model_key_configured"):
    st.info("智能服务尚未配置，暂时无法生成计划。您可以先保存个人资料。")
elif not runtime.get("vector_index_ready"):
    if runtime.get("embedding_key_configured") is False:
        st.info("聊天服务已配置，但食品检索服务尚未配置。完成食品检索配置和索引准备后，即可生成包含饮食的完整计划。")
    else:
        st.info("食品搜索索引尚未建立，完成准备后即可生成计划。")
if st.button("🚀 生成完整计划", use_container_width=True, type="primary", disabled=not runtime.get("ready", False)):
    with st.spinner("🤖 正在为您编排健身计划…"):
        # Show progress steps
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("🔄 正在准备您的计划…")
        progress_bar.progress(20)

        result = FitnessAPI.generate_langgraph_plan(
            st.session_state.user_id, use_o3_mini, use_full_database, meal_plan_days
        )

        if result and result.get("workflow_status") == "completed":
            status_text.text("✅ 计划生成完成！")
            progress_bar.progress(100)
        elif result:
            status_text.text("计划未全部完成，请查看下方提示。")

    if result:
        if result.get("workflow_status") == "completed":
            st.success("✅ 您的完整健身计划已生成！")
        else:
            st.warning("计划未全部完成，以下仅展示已成功生成的部分。")

        # Show workflow execution steps
        if result.get("execution_steps"):
            with st.expander("🔍 计划生成步骤", expanded=False):
                for i, step in enumerate(result["execution_steps"], 1):
                    st.write(f"{i}. {step}")

        # Show any errors
        if result.get("errors"):
            st.warning("⚠️ 生成过程中出现以下问题：")
            for error in result["errors"]:
                st.write(f"- {error}")

        # Display the summary
        if result.get("summary"):
            st.subheader("🎯 您的个性化计划总结")
            st.markdown(result["summary"])

        # Meal Plan Section
        if result.get("meal_plan"):
            st.subheader("🍽️ 饮食计划")
            meal_plan = result["meal_plan"]

            # Display plan name and overview
            if meal_plan.get("plan_name"):
                st.markdown(f"**{meal_plan['plan_name']}**")

            if meal_plan.get("target_macros"):
                st.markdown("**每日目标：**")

                col1, col2, col3, col4 = st.columns(4)

                macros = meal_plan["target_macros"]
                with col1:
                    st.metric("热量", f"{macros.get('calories', 0):,.0f}")
                with col2:
                    st.metric("蛋白质", f"{macros.get('protein_g', 0):.0f}g")
                with col3:
                    st.metric("碳水化合物", f"{macros.get('carbs_g', 0):.0f}g")
                with col4:
                    st.metric("脂肪", f"{macros.get('fat_g', 0):.0f}g")

            # Display daily meal plans in structured format
            if meal_plan.get("daily_plans"):
                plan_days = len(meal_plan["daily_plans"])
                with st.expander(
                    f"📋 {plan_days} 天详细饮食计划", expanded=True
                ):
                    for day_plan in meal_plan["daily_plans"]:
                        day_name = (
                            day_plan.get("day_name")
                            or f"第 {day_plan.get('day', '?')} 天"
                        )
                        st.markdown(f"### {day_name}")

                        # Display meals for this day
                        for meal in day_plan.get("meals", []):
                            st.markdown(f"**{meal.get('meal_name', '餐食')}**")

                            # Display foods in this meal
                            for food in meal.get("foods", []):
                                st.write(
                                    f"• {food.get('food_name', '食物')} - {food.get('portion', '暂无')} "
                                    f"({food.get('calories', 0):.0f} 千卡, "
                                    f"{food.get('protein_g', 0):.1f}克蛋白质)"
                                )

                            # Display meal totals
                            meal_macros = meal.get("total_macros", {})
                            if meal_macros:
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.caption(
                                        f"🔥 {meal_macros.get('calories', 0):.0f} 千卡"
                                    )
                                with col2:
                                    st.caption(
                                        f"🥩 {meal_macros.get('protein_g', 0):.1f}g"
                                    )
                                with col3:
                                    st.caption(
                                        f"🍞 {meal_macros.get('carbs_g', 0):.1f}g"
                                    )
                                with col4:
                                    st.caption(f"🥑 {meal_macros.get('fat_g', 0):.1f}g")

                            # Preparation notes
                            if meal.get("preparation_notes"):
                                st.caption(f"📝 {meal['preparation_notes']}")

                            st.markdown("---")

                        # Daily totals
                        daily_totals = day_plan.get("daily_totals", {})
                        if daily_totals:
                            st.markdown("**每日合计：**")
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric(
                                    "热量", f"{daily_totals.get('calories', 0):.0f}"
                                )
                            with col2:
                                st.metric(
                                    "蛋白质",
                                    f"{daily_totals.get('protein_g', 0):.1f}g",
                                )
                            with col3:
                                st.metric(
                                    "碳水化合物", f"{daily_totals.get('carbs_g', 0):.1f}g"
                                )
                            with col4:
                                st.metric("脂肪", f"{daily_totals.get('fat_g', 0):.1f}g")

                        st.markdown("---")

            # Display key principles and shopping tips
            col1, col2 = st.columns(2)

            with col1:
                if meal_plan.get("key_principles"):
                    st.markdown("**🎯 基本原则：**")
                    for principle in meal_plan["key_principles"]:
                        st.write(f"• {principle}")

            with col2:
                if meal_plan.get("shopping_tips"):
                    st.markdown("**🛒 采购建议：**")
                    for tip in meal_plan["shopping_tips"]:
                        st.write(f"• {tip}")

            # Show metadata
            if meal_plan.get("available_foods_count"):
                st.caption(
                    f"📊 本计划基于数据库中的 {meal_plan['available_foods_count']} 种可用食物生成"
                )

        # Workout Plan Section
        if result.get("workout_plan"):
            st.subheader("💪 训练计划")
            workout_plan = result["workout_plan"]

            # Display plan name and overview
            if workout_plan.get("plan_name"):
                st.markdown(f"**{workout_plan['plan_name']}**")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("训练方式", workout_plan.get("training_style", "暂无"))
            with col2:
                st.metric("训练分化方式", workout_plan.get("split_type", "暂无"))
            with col3:
                st.metric("每周天数", workout_plan.get("days_per_week", "暂无"))
            with col4:
                duration = workout_plan.get("duration_minutes", "暂无")
                st.metric("时长", f"{duration} 分钟" if duration != "暂无" else "暂无")

            # Display weekly schedule in structured format
            if workout_plan.get("weekly_schedule"):
                with st.expander("🏋️‍♂️ 每周训练安排", expanded=True):
                    for workout_day in workout_plan["weekly_schedule"]:
                        day_name = (
                            workout_day.get("day_name")
                            or f"第 {workout_day.get('day', '?')} 天"
                        )
                        st.markdown(
                            f"### {day_name} - {workout_day.get('focus', '训练')}"
                        )

                        # Warm-up
                        if workout_day.get("warm_up"):
                            st.markdown("**🔥 热身：**")
                            for warmup in workout_day["warm_up"]:
                                st.write(f"• {warmup}")

                        # Main exercises
                        if workout_day.get("exercises"):
                            st.markdown("**💪 训练动作：**")

                            # Create table-like display for exercises
                            ex_col1, ex_col2, ex_col3, ex_col4 = st.columns(
                                [3, 1, 1, 2]
                            )

                            with ex_col1:
                                st.write("**动作**")
                            with ex_col2:
                                st.write("**组数**")
                            with ex_col3:
                                st.write("**次数**")
                            with ex_col4:
                                st.write("**休息**")

                            st.markdown("---")

                            for exercise in workout_day["exercises"]:
                                ex_col1, ex_col2, ex_col3, ex_col4 = st.columns(
                                    [3, 1, 1, 2]
                                )

                                with ex_col1:
                                    st.write(exercise.get("exercise_name", "动作"))
                                    if exercise.get("notes"):
                                        st.caption(f"💡 {exercise['notes']}")
                                with ex_col2:
                                    st.write(str(exercise.get("sets", "暂无")))
                                with ex_col3:
                                    st.write(str(exercise.get("reps", "暂无")))
                                with ex_col4:
                                    rest_time = exercise.get("rest_seconds", 0)
                                    if rest_time >= 60:
                                        st.write(
                                            f"{rest_time // 60} 分 {rest_time % 60} 秒"
                                        )
                                    else:
                                        st.write(f"{rest_time} 秒")

                        # Cool-down
                        if workout_day.get("cool_down"):
                            st.markdown("**🧘 放松整理：**")
                            for cooldown in workout_day["cool_down"]:
                                st.write(f"• {cooldown}")

                        # Estimated duration
                        if workout_day.get("estimated_duration"):
                            st.caption(
                                f"⏱️ 预计时长：{workout_day['estimated_duration']} 分钟"
                            )

                        st.markdown("---")

            # Display additional workout plan info
            col1, col2 = st.columns(2)

            with col1:
                if workout_plan.get("key_principles"):
                    st.markdown("**🎯 训练原则：**")
                    for principle in workout_plan["key_principles"]:
                        st.write(f"• {principle}")

                if workout_plan.get("progression_strategy"):
                    st.markdown("**📈 进阶策略：**")
                    st.write(workout_plan["progression_strategy"])

            with col2:
                if workout_plan.get("equipment_needed"):
                    st.markdown("**🛠️ 所需器械：**")
                    for equipment in workout_plan["equipment_needed"]:
                        st.write(f"• {equipment}")

        # Plan metadata
        if result.get("generated_at"):
            st.caption(f"计划生成时间： {result['generated_at']}")

        st.balloons()

# Footer
render_footer()
