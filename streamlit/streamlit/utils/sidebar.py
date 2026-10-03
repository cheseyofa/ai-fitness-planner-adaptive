import streamlit as st


def render_sidebar_disclaimer():
    """Render the disclaimer in the sidebar as an expander, default closed"""

    st.markdown("""<style>
        [data-testid="stToolbar"], [data-testid="stStatusWidget"],
        #MainMenu, .stAppDeployButton {display: none !important;}
    </style>""", unsafe_allow_html=True)
    with st.sidebar:
        st.caption("智能健身助手 · 中文版")
        with st.expander("⚠️ 重要声明", expanded=False):
            st.markdown(
                """
                **仅供教学与演示**
                
                本应用仅用于教学和演示。 
                本系统生成的饮食计划、营养建议和训练建议 
                **不构成医疗或专业健康建议**。
                
                **开始新的饮食或运动计划前，请咨询合格的医疗专业人员、注册营养师 
                或认证健身教练。** 
                个人效果可能不同，本工具不能替代专业医疗指导。
                """,
                help="本声明适用于本应用生成的所有内容。",
            )
