"""
主框架页面 - 只负责登录检查、侧边栏和页面导航
聊天功能在 manage_account.py 中
"""

import streamlit as st
import io
import os
from PIL import Image
from login import login_and_register, check_login

# ========== 页面配置 ==========
st.set_page_config(
    page_title="智能助手",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========== 会话状态初始化 ==========
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if "messages" not in st.session_state:
    st.session_state.messages = {}

if "chat_bot" not in st.session_state["messages"]:
    st.session_state["messages"]["chat_bot"] = []

if "online" not in st.session_state:
    st.session_state.online = False

if "model_provider" not in st.session_state:
    st.session_state.model_provider = "cloud"

if "local_model_name" not in st.session_state:
    st.session_state.local_model_name = "qwen2.5:3b"

if "cloud_model_name" not in st.session_state:
    st.session_state.cloud_model_name = "deepseek-v4-flash"

if "search_provider" not in st.session_state:
    st.session_state.search_provider = "duckduckgo"

if "show_thinking" not in st.session_state:
    st.session_state.show_thinking = False


# ========== 登录检查 ==========
def logout():
    st.session_state.logged_in_user = None
    st.session_state.messages = {}
    # 回调中不需要调用 st.rerun()，Streamlit 会自动触发 rerun


if not check_login():
    login_and_register(key_prefix="main")
    st.stop()

# ========== 侧边栏用户信息（导航栏上方）==========
with st.sidebar:
    # 用户信息卡片 - 放在最上方
    st.markdown(
        f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px; padding: 1rem; color: white; margin-bottom: 0.5rem;">
        <div style="font-size: 0.85rem; opacity: 0.9;">👋 欢迎回来 &nbsp;{st.session_state.logged_in_user}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.button("🚪 退出登录", on_click=logout, use_container_width=True)
    st.divider()

    # 联系方式
    with st.expander("📞 联系我"):
        image_path = r"./images/微信图片_20250803180325.jpg"
        try:
            image = Image.open(image_path)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format="JPEG")
            st.image(image_bytes, caption="扫码添加微信", use_container_width=True)
        except Exception as e:
            st.warning(f"图片加载失败: {e}")


# ========== 导航页面定义 ==========
def history_items():
    """历史记录页面"""
    st.title("📜 聊天历史记录")
    st.write("以下是您的聊天记录：")
    if st.session_state.messages.get("chat_bot"):
        st.json(st.session_state.messages["chat_bot"])
    else:
        st.info("暂无聊天记录")


# 页面导航配置
pages = {
    "首页": [
        st.Page("manage_account.py", title="💬 开始聊天"),
        st.Page("pages/4_检索页.py", title="📄 文档检索"),
    ],
    "功能": [
        st.Page("trial.py", title="🎯 功能体验"),
        st.Page("pages/1_记账页.py", title="💰 记账本"),
        st.Page("pages/2_统计页.py", title="📊 统计分析"),
    ],
    "更多": [
        st.Page("learn.py", title="📖 关于我们"),
        st.Page("pages/3_信息页.py", title="👤 个人信息"),
        st.Page(history_items, title="📜 历史记录"),
    ],
}

pg1 = st.navigation(pages, position="sidebar")
pg1.run()
