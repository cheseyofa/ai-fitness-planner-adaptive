import streamlit as st
import requests
from utils.labels import label
from utils.api_client import FitnessAPI, init_session_state
from utils.footer import render_footer
from utils.sidebar import render_sidebar_disclaimer

# Configure page
st.set_page_config(
    page_title="食物搜索 - 智能健身助手", page_icon="🔍", layout="wide"
)

# Initialize session state and setup sidebar
init_session_state()

# Add disclaimer to sidebar
render_sidebar_disclaimer()

st.header("🔍 食物数据库搜索")
st.markdown(
    "输入中文食物名称或描述需求，按营养目标查找食物。数据主要来自美国食品营养数据库，食品原始名称可能为英文。"
)


def display_search_results(results):
    """Display basic search results"""
    for i, food in enumerate(results):
        with st.expander(
            f"🥘 {food.get('description', '未知食物')} - {food.get('brand_owner', '未知品牌')}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**产品信息：**")
                st.write(f"**品牌：** {food.get('brand_name', '暂无')}")
                st.write(f"**分类：** {food.get('food_category', '暂无')}")
                st.write(
                    f"**每份份量：** {food.get('serving_size', '暂无')} {food.get('serving_size_unit', '')}"
                )

                if food.get("ingredients"):
                    st.write(
                        f"**配料：** {food['ingredients'][:200]}{'...' if len(food['ingredients']) > 200 else ''}"
                    )

            with col2:
                nutrition = food.get("nutrition_enhanced", {})
                per_100g = nutrition.get("per_100g", {})

                if per_100g:
                    st.markdown("**每 100 克营养成分：**")

                    metrics_col1, metrics_col2 = st.columns(2)
                    with metrics_col1:
                        st.metric("热量", f"{per_100g.get('energy_kcal', 0)} kcal")
                        st.metric("蛋白质", f"{per_100g.get('protein_g', 0)} g")
                    with metrics_col2:
                        st.metric("碳水化合物", f"{per_100g.get('carbs_g', 0)} g")
                        st.metric("脂肪", f"{per_100g.get('total_fat_g', 0)} g")

                    macro_breakdown = nutrition.get("macro_breakdown", {})
                    if macro_breakdown.get("primary_macro_category"):
                        st.write(
                            f"**主要营养素：** {label(macro_breakdown['primary_macro_category'])}"
                        )
                else:
                    st.warning("暂无营养数据")


def display_semantic_results(results):
    """Display semantic search results with similarity scores"""
    for i, food in enumerate(results):
        similarity_score = food.get("similarity_score", 0)
        score_color = (
            "🟢" if similarity_score > 0.8 else "🟡" if similarity_score > 0.7 else "🟠"
        )

        with st.expander(
            f"{score_color} {food.get('description', '未知食物')} - {food.get('brand_owner', '未知品牌')} (匹配度： {similarity_score:.1%})"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**产品信息：**")
                st.write(f"**品牌：** {food.get('brand_name', '暂无')}")
                st.write(f"**分类：** {food.get('food_category', '暂无')}")
                st.write(f"**每份份量：** {food.get('serving_size', 0)} g")

                # Show what matched - fixed: no nested expanders
                if food.get("matched_content"):
                    st.markdown("**📄 匹配依据：**")
                    with st.container():
                        st.caption(food["matched_content"])

            with col2:
                nutrition = food.get("nutrition_per_100g", {})

                st.markdown("**每 100 克营养成分：**")

                metrics_col1, metrics_col2 = st.columns(2)
                with metrics_col1:
                    st.metric("热量", f"{nutrition.get('calories', 0):.0f} kcal")
                    st.metric("蛋白质", f"{nutrition.get('protein_g', 0):.1f} g")
                with metrics_col2:
                    st.metric("碳水化合物", f"{nutrition.get('carbs_g', 0):.1f} g")
                    st.metric("脂肪", f"{nutrition.get('fat_g', 0):.1f} g")

                # Additional info
                primary_macro = food.get("primary_macro_category", "unknown")
                if primary_macro != "unknown":
                    st.write(
                        f"**主要营养素：** {label(primary_macro)}"
                    )

                if food.get("is_high_protein"):
                    st.info("💪 高蛋白食物")


def display_hybrid_results(results):
    """Display hybrid search results with scoring breakdown"""
    for i, food in enumerate(results):
        hybrid_score = food.get("hybrid_score", 0)
        semantic_score = food.get("semantic_score", 0)
        traditional_score = food.get("traditional_score", 0)

        score_icon = (
            "🥇" if hybrid_score > 0.8 else "🥈" if hybrid_score > 0.6 else "🥉"
        )

        with st.expander(
            f"{score_icon} {food.get('description', '未知食物')} - {food.get('brand_owner', '未知品牌')} (评分： {hybrid_score:.2f})"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**产品信息：**")
                st.write(f"**品牌：** {food.get('brand_name', '暂无')}")
                st.write(f"**分类：** {food.get('food_category', '暂无')}")
                st.write(f"**每份份量：** {food.get('serving_size', 0)} g")

                # Show scoring breakdown - improved layout
                st.markdown("**搜索评分：**")
                score_col1, score_col2 = st.columns(2)
                with score_col1:
                    st.metric("🧠 需求匹配分", f"{semantic_score:.2f}")
                    st.metric("📝 文本评分", f"{traditional_score:.2f}")
                with score_col2:
                    st.metric("🎯 综合评分", f"{hybrid_score:.2f}")

            with col2:
                nutrition = food.get("nutrition_per_100g", {})

                st.markdown("**每 100 克营养成分：**")

                metrics_col1, metrics_col2 = st.columns(2)
                with metrics_col1:
                    st.metric("热量", f"{nutrition.get('calories', 0):.0f} kcal")
                    st.metric("蛋白质", f"{nutrition.get('protein_g', 0):.1f} g")
                with metrics_col2:
                    st.metric("碳水化合物", f"{nutrition.get('carbs_g', 0):.1f} g")
                    st.metric("脂肪", f"{nutrition.get('fat_g', 0):.1f} g")

                # Additional info
                primary_macro = food.get("primary_macro_category", "unknown")
                if primary_macro != "unknown":
                    st.write(
                        f"**主要营养素：** {label(primary_macro)}"
                    )

                if food.get("is_high_protein"):
                    st.info("💪 高蛋白食物")

                nutrition_density = food.get("nutrition_density_score", 0)
                if nutrition_density > 0:
                    st.metric("🎯 营养密度", f"{nutrition_density:.1f}")


# Database selection
# st.subheader("📊 Database Settings")
# use_full_database = st.checkbox(
#     "Use full USDA database",
#     value=False,
#     help="Use the complete USDA database vs the sample dataset. Requires full database to be imported."
# )
use_full_database = False
# Database availability check
if use_full_database:
    try:
        db_status = FitnessAPI.check_database_availability()
        if not db_status.get("full_database", {}).get("available", False):
            st.error(
                "❌ 完整 USDA 数据库不可用，目前仅提供样本数据。"
                "请先导入完整数据库，或关闭完整数据库选项。"
            )
            use_full_database = False  # Override to use sample
        else:
            st.success(
                f"✅ 完整数据库可用，共 {db_status['full_database']['document_count']:,} 种食物"
            )
    except Exception as e:
        st.warning(f"⚠️ 无法检查数据库状态： {str(e)}")
        use_full_database = False
else:
    try:
        db_status = FitnessAPI.check_database_availability()
        sample_count = db_status.get("sample_database", {}).get("document_count", 0)
        if sample_count > 0:
            st.info(f"📋 正在使用样本数据库，共 {sample_count:,} 种食物")
    except:
        pass

# Search method selection
search_method = st.radio(
    "搜索方式：",
    ["🔍 基础搜索", "🧠 按需求搜索", "🎯 高级筛选"],
    horizontal=True,
    help="可以直接输入食物名称，也可以描述饮食需求，或设置具体的营养条件。",
)

if search_method == "🔍 基础搜索":
    # Basic search interface
    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            "搜索食物：",
            placeholder="例如：鸡胸肉、酸奶、燕麦…",
            key="basic_query",
        )

    with col2:
        search_limit = st.selectbox("结果数量", [5, 10, 20], index=1)

    if st.button("🔍 搜索食物", use_container_width=True) and search_query:
        with st.spinner("正在搜索营养数据库…"):
            results = FitnessAPI.search_nutrition(search_query, search_limit)

            if results and results.get("results"):
                st.success(
                    f"“{search_query}”共找到 {results['results_found']} 条结果"
                )
                display_semantic_results(results["results"])
            else:
                st.warning("未找到结果，请尝试其他关键词！")

elif search_method == "🧠 按需求搜索":
    # Semantic search interface
    st.markdown("### 🧠 用一句话描述需求")
    st.info(
        "用自然语言描述需求，例如“高蛋白早餐”或“适合生酮饮食的低碳水零食”。"
    )

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        semantic_query = st.text_input(
            "描述您的食物需求：",
            placeholder="例如：高蛋白低碳水早餐、训练后恢复餐…",
            key="semantic_query",
        )

    with col2:
        similarity_threshold = st.slider(
            "匹配精度",
            min_value=0.5,
            max_value=1.0,
            value=0.7,
            step=0.05,
            help="数值越高，匹配要求越严格",
        )

    with col3:
        semantic_limit = st.selectbox(
            "结果数量", [5, 10, 15, 20], index=1, key="semantic_limit"
        )

    # Dietary restrictions
    with st.expander("🥗 饮食限制（选填）"):
        col1, col2, col3 = st.columns(3)

        with col1:
            vegan = st.checkbox("纯素")
        with col2:
            vegetarian = st.checkbox("素食")
        with col3:
            gluten_free = st.checkbox("无麸质")

    if st.button("🧠 按需求搜索", use_container_width=True) and semantic_query:
        # Build dietary restrictions list
        restrictions = []
        if vegan:
            restrictions.append("vegan")
        if vegetarian:
            restrictions.append("vegetarian")
        if gluten_free:
            restrictions.append("gluten-free")

        with st.spinner("正在进行 用一句话描述需求…"):
            try:
                api_url = FitnessAPI.get_api_url()
                request_data = {
                    "query": semantic_query,
                    "dietary_restrictions": restrictions,
                    "macro_goals": {},
                    "limit": semantic_limit,
                    "similarity_threshold": similarity_threshold,
                    "use_full_database": use_full_database,
                }

                response = requests.post(
                    f"{api_url}/v1/nutrition_search/search_nutrition_semantic/",
                    json=request_data,
                    timeout=30,
                )

                if response.status_code == 200:
                    results = response.json()
                    st.success(
                        f"找到 {results['results_found']} 条匹配结果，耗时 {results['search_time_ms']} 毫秒"
                    )
                    display_semantic_results(results["results"])
                else:
                    st.error("搜索暂时不可用，请稍后重试或联系维护人员检查数据服务。")

            except Exception as e:
                st.error("语义搜索出错： 服务暂时不可用，请稍后重试或联系维护人员。")

elif search_method == "🎯 高级筛选":
    # Advanced nutrition-based search
    st.markdown("### 🎯 按营养目标搜索")
    st.info("查找符合指定营养条件的食物")

    col1, col2 = st.columns([2, 1])

    with col1:
        advanced_query = st.text_input(
            "食物名称或描述：",
            placeholder="例如：蛋白粉、鸡肉、燕麦…",
            key="advanced_query",
        )

    with col2:
        hybrid_limit = st.selectbox(
            "结果数量", [5, 10, 15, 20], index=1, key="hybrid_limit"
        )

    # Nutrition filters
    st.markdown("#### 🥇 营养目标（每 100 克）")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        protein_min = st.number_input(
            "最低蛋白质（克）", min_value=0.0, max_value=100.0, value=0.0, step=1.0
        )

    with col2:
        carbs_max = st.number_input(
            "最高碳水化合物（克）", min_value=0.0, max_value=100.0, value=100.0, step=1.0
        )

    with col3:
        calories_max = st.number_input(
            "最高热量（千卡）", min_value=0, max_value=1000, value=1000, step=10
        )

    with col4:
        semantic_weight = st.slider(
            "需求理解占比",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="数值越高，越注重理解您的需求；数值越低，越注重关键词是否一致。",
        )

    # Dietary restrictions for advanced search
    with st.expander("🥗 饮食限制（选填）"):
        selected_restrictions = st.multiselect(
            "请选择需要避免的食物类型",
            ["vegan", "vegetarian", "gluten-free", "dairy-free"],
            format_func=label,
            help="可选择多项，不需要输入英文。",
        )
        restrictions_text = ",".join(selected_restrictions)

    if st.button("🎯 高级搜索", use_container_width=True) and advanced_query:
        with st.spinner("正在按营养条件搜索…"):
            try:
                api_url = FitnessAPI.get_api_url()

                params = {
                    "query": advanced_query,
                    "dietary_restrictions": restrictions_text,
                    "protein_min": protein_min,
                    "carbs_max": carbs_max,
                    "calories_max": calories_max,
                    "limit": hybrid_limit,
                    "semantic_weight": semantic_weight,
                    "use_full_database": use_full_database,
                }

                response = requests.get(
                    f"{api_url}/v1/nutrition_search/search_nutrition_hybrid/",
                    params=params,
                    timeout=30,
                )

                if response.status_code == 200:
                    results = response.json()
                    st.success(
                        f"找到 {results['results_found']} 种符合条件的食物"
                    )

                    # Show search weights
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "需求理解占比", f"{results['semantic_weight']:.0%}"
                        )
                    with col2:
                        st.metric(
                            "文字匹配占比", f"{results['traditional_weight']:.0%}"
                        )

                    display_hybrid_results(results["results"])
                else:
                    st.error("搜索暂时不可用，请稍后重试或联系维护人员检查数据服务。")

            except Exception as e:
                st.error("高级搜索出错： 服务暂时不可用，请稍后重试或联系维护人员。")

# Add help section
with st.expander("❓ 搜索帮助"):
    st.markdown(
        """
    ### 搜索类型：
    
    **🔍 基础搜索:** 按食物名称或品牌检索数据库
    - 适合：查找已知名称的食物
    - 示例：鸡胸肉、希腊酸奶
    
    **🧠 按需求搜索:** 使用 AI 理解自然语言需求
    - 适合：描述您的营养需求
    - 示例：“高蛋白早餐”“低碳水生酮零食”
    
    **🎯 高级筛选:** 结合 AI 搜索与具体营养条件
    - 适合：查找符合明确营养目标的食物
    - 示例：查找每 100 克中蛋白质高于 20 克、碳水化合物低于 5 克的食物
    
    ### 使用建议：
    - 使用具体的关键词，有助于获得更准确的结果
    - 未找到所需食物时，可以尝试其他搜索方式
    - 按需求搜索适合输入完整描述
    - 高级筛选可以缩小结果范围
    """
    )

# Footer
render_footer()
