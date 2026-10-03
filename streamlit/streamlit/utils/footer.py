import streamlit as st
from datetime import datetime


def render_footer():
    st.divider()
    st.caption(f"智能健身助手 · 原作者：Josh Janzen · © {datetime.now().year}")
    st.caption("教学演示应用，不用于商业用途。健康与训练建议请结合专业人员的指导。")
