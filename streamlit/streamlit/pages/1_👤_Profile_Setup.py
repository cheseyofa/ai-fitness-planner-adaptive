import streamlit as st
from utils.labels import label
from datetime import datetime
from utils.api_client import FitnessAPI, init_session_state
from utils.footer import render_footer
from utils.sidebar import render_sidebar_disclaimer


# Unit conversion functions
def kg_to_lbs(kg):
    """Convert kilograms to pounds"""
    return kg * 2.20462


def lbs_to_kg(lbs):
    """Convert pounds to kilograms"""
    return lbs / 2.20462


def cm_to_ft_in(cm):
    """Convert centimeters to feet and inches"""
    total_inches = cm / 2.54
    feet = int(total_inches // 12)
    inches = total_inches % 12
    return feet, inches


def ft_in_to_cm(feet, inches):
    """Convert feet and inches to centimeters"""
    total_inches = feet * 12 + inches
    return total_inches * 2.54


# Configure page
st.set_page_config(
    page_title="个人资料 - 智能健身助手", page_icon="👤", layout="wide"
)

# Initialize session state and setup sidebar
init_session_state()

# Add disclaimer to sidebar
render_sidebar_disclaimer()

st.header("👤 个人资料设置")
st.markdown("填写个人资料，开始定制您的健身计划！")

# Test API connection first
current_api_url = FitnessAPI.get_api_url()
connection_test = FitnessAPI.test_connection()
if not connection_test["success"]:
    st.error("❌ 暂时无法连接服务，请稍后重试或联系维护人员。")

    st.markdown(
        """
    **排查建议：**
    1. 检查网络连接
    2. 点击下方按钮重新连接
    3. 如果仍无法连接，请联系维护人员启动服务
    """
    )

    if st.button("🔄 重新连接"):
        st.rerun()
    st.stop()
else:
    st.success("✅ 已连接服务")

# Check if profile exists
with st.spinner("正在查找已有资料…"):
    existing_profile = FitnessAPI.get_profile(st.session_state.user_id)

if existing_profile:
    st.success("✅ 已找到个人资料，您可以在下方修改。")
    st.session_state.current_profile = existing_profile
else:
    st.info(
        "🆕 尚未找到个人资料。请先填写资料，开始定制健身计划！"
    )

st.subheader("基本信息")

# Unit system selection
unit_system = st.selectbox(
    "计量单位",
    ["Imperial (lbs/ft)", "Metric (kg/cm)"],
    index=1,  # Default to metric units for Chinese users.
    help="默认使用千克和厘米。1 千克等于 2 斤。",
                  format_func=label,
)

is_metric = unit_system.startswith("Metric")

with st.form("profile_form"):
    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input(
            "年龄", min_value=16, max_value=80, value=existing_profile.get("age", 35)
        )

        if is_metric:
            weight_input = st.number_input(
                "体重（千克）",
                min_value=40.0,
                max_value=200.0,
                value=existing_profile.get("weight", 70.0),
                step=0.5,
            )
            weight_kg = weight_input
        else:
            # Convert existing weight from kg to lbs for display
            existing_weight_lbs = kg_to_lbs(existing_profile.get("weight", 80.0))
            weight_input = st.number_input(
                "体重（磅）",
                min_value=88.0,  # ~40kg
                max_value=440.0,  # ~200kg
                value=existing_weight_lbs,
                step=1.0,
            )
            weight_kg = lbs_to_kg(weight_input)

        activity_level = st.selectbox(
            "日常活动强度",
            ["sedentary", "light", "moderate", "active", "very_active"],
            index=["sedentary", "light", "moderate", "active", "very_active"].index(
                existing_profile.get("activity_level", "moderate")
            ),
                             format_func=label,
        )

    with col2:
        if is_metric:
            height_input = st.number_input(
                "身高（厘米）",
                min_value=140.0,
                max_value=220.0,
                value=existing_profile.get("height", 182.0),
                step=0.5,
            )
            height_cm = height_input
        else:
            # Convert existing height from cm to feet and inches for display
            existing_height_cm = existing_profile.get("height", 182.0)
            existing_feet, existing_inches = cm_to_ft_in(existing_height_cm)

            col_ft, col_in = st.columns(2)
            with col_ft:
                height_feet = st.number_input(
                    "身高（英尺）",
                    min_value=4,
                    max_value=7,
                    value=int(existing_feet),
                    step=1,
                )
            with col_in:
                height_inches = st.number_input(
                    "身高（英寸）",
                    min_value=0.0,
                    max_value=11.9,
                    value=existing_inches,
                    step=0.1,
                )
            height_cm = ft_in_to_cm(height_feet, height_inches)

        fitness_goal = st.selectbox(
            "主要目标",
            ["cut", "bulk", "maintenance", "recomp"],
            index=["cut", "bulk", "maintenance", "recomp"].index(
                existing_profile.get("fitness_goal", "maintenance")
            ),
                           format_func=label,
        )

        # Add expander with goal explanations in sidebar
        with st.sidebar:
            with st.expander("ℹ️ 健身目标说明"):
                st.markdown(
                    """
                **减脂** 🔥
                - 减少脂肪，同时尽量保留肌肉
                - 热量摄入减少 20%
                - 优先选择低脂蛋白质来源
                - 通常较快看到体型变化
                
                **增肌** 💪
                - 增加肌肉与体重
                - 热量摄入增加 20%
                - 注重蛋白质摄入
                - 可能伴随一定脂肪增长
                
                **维持体重** ⚖️
                - 保持当前体重
                - 均衡安排营养摄入
                - 适合长期坚持
                - 适合初学者
                
                **体态重塑** 🎯
                - 同时增肌和减脂
                - 维持热量摄入
                - 注重高蛋白饮食
                - 变化较慢，注重身体成分改善
                """
                )
                st.info(
                    "💡 **提示：** 体态重塑更适合初学者或中断训练后重新开始的人群！"
                )

        workout_frequency = st.number_input(
            "每周训练天数",
            min_value=1,
            max_value=7,
            value=existing_profile.get("workout_frequency", 3),
        )

    st.subheader("偏好与限制")

    allergies = st.multiselect(
        "过敏或不耐受食物",
        ["dairy", "gluten", "nuts", "shellfish", "eggs", "soy"],
        default=existing_profile.get("allergies", []),
                    format_func=label,
    )

    dietary_preferences = st.multiselect(
        "饮食偏好",
        ["vegetarian", "vegan", "keto", "paleo", "mediterranean", "low_carb"],
        default=existing_profile.get("dietary_preferences", []),
                              format_func=label,
    )

    equipment_available = st.multiselect(
        "可用训练器械",
        [
            "bodyweight",
            "dumbbells",
            "barbell",
            "resistance_bands",
            "pull_up_bar",
            "gym_access",
        ],
        default=existing_profile.get(
            "equipment_available", ["bodyweight", "dumbbells"]
        ),
                              format_func=label,
    )

    # Show conversion info for imperial users
    if not is_metric:
        st.info(
            f"📊 换算后的身体指标：体重 {weight_kg:.1f} 千克，身高 {height_cm:.1f} 厘米"
        )

    submitted = st.form_submit_button("💾 保存资料", use_container_width=True)

    if submitted:
        profile_data = {
            "user_id": st.session_state.user_id,
            "age": age,
            "weight": weight_kg,  # Always send metric to API
            "height": height_cm,  # Always send metric to API
            "activity_level": activity_level,
            "fitness_goal": fitness_goal,
            "workout_frequency": workout_frequency,
            "allergies": allergies,
            "dietary_preferences": dietary_preferences,
            "equipment_available": equipment_available,
            "created_at": (
                datetime.now().isoformat()
                if not existing_profile
                else existing_profile.get("created_at")
            ),
        }

        with st.spinner("正在保存资料并计算营养需求…"):
            result = FitnessAPI.create_profile(profile_data)

            if result:
                st.success("✅ 个人资料保存成功！")
                st.session_state.profile_created = True
                st.session_state.current_profile = result

                # Display calculated macros
                st.subheader("🎯 您的每日目标")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("每日热量", f"{result.get('target_calories', 0):,}")

                with col2:
                    st.metric("蛋白质", f"{result.get('target_protein_g', 0)}g")

                with col3:
                    st.metric("碳水化合物", f"{result.get('target_carbs_g', 0)}g")

                with col4:
                    st.metric("脂肪", f"{result.get('target_fat_g', 0)}g")

                st.balloons()

# Footer
render_footer()
