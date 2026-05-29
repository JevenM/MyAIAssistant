import hmac
import streamlit as st
import json
import os
import uuid

USER_FILE = "users.json"


# 加载用户数据
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 保存用户数据
def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def check_login():
    """统一的登录检查函数，所有页面都应该调用此函数"""
    if "logged_in_user" not in st.session_state or not st.session_state.logged_in_user:
        return False
    return True


def require_login():
    """需要登录的页面调用此函数，未登录时显示登录界面并停止执行"""
    if not check_login():
        login_and_register()
        st.stop()


def login_and_register(show_warning=True, key_prefix=None):
    """
    显示登录/注册界面

    Args:
        show_warning: 是否显示警告提示
        key_prefix: 表单 key 前缀，用于避免重复 key 错误
    """
    # 生成唯一的 key 前缀
    if key_prefix is None:
        key_prefix = str(uuid.uuid4())[:8]

    # 隐藏侧边栏和自定义样式
    st.markdown(
        """
    <style>
        /* 隐藏侧边栏 */
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="stSidebarNav"] {
            display: none;
        }
        /* 登录页面样式 */
        .login-header {
            text-align: center;
            padding: 2rem 0;
        }
        .login-title {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(120deg, #ff6b6b, #feca57, #48dbfb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # 登录页面标题
    st.markdown(
        """
    <div class="login-header">
        <div class="login-title">🧊 小橙子智能助手</div>
        <p style="color: #666; margin-top: 0.5rem;">欢迎回来，请登录或注册</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    user_dict = load_users()
    tab1, tab2 = st.tabs(["🔐 登录账号", "🆕 注册账号"])

    with tab1:
        # 登录表单
        default_username = st.session_state.get("remember_me", "")

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            username = st.text_input(
                "用户名",
                key=f"{key_prefix}_login_username",
                value=default_username,
                placeholder="请输入用户名",
            )
            password = st.text_input(
                "密码",
                type="password",
                key=f"{key_prefix}_login_password",
                placeholder="请输入密码",
            )
            remember = st.checkbox(
                "记住我的登录状态",
                key=f"{key_prefix}_remember_checkbox",
                value=bool(default_username),
            )

            if st.button(
                "🚀 登录", key=f"{key_prefix}_login_btn", use_container_width=True
            ):
                if username in user_dict and hmac.compare_digest(
                    password,
                    user_dict[username],
                ):
                    st.session_state.logged_in_user = username
                    if remember:
                        st.session_state["remember_me"] = username
                    else:
                        st.session_state.pop("remember_me", None)

                    # 登录成功后加载用户数据
                    from user_data_manager import load_user_data_to_session
                    load_user_data_to_session(username, st.session_state)

                    st.success("✅ 登录成功！欢迎回来~")
                    st.rerun()
                else:
                    st.error("❌ 用户名或密码错误，请重试")

            if show_warning and "logged_in_user" not in st.session_state:
                st.info("👋 请先登录后再使用本系统")

    with tab2:
        # 注册表单
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            new_username = st.text_input(
                "用户名",
                key=f"{key_prefix}_register_username",
                placeholder="请设置用户名",
            )
            new_password = st.text_input(
                "密码",
                type="password",
                key=f"{key_prefix}_register_password",
                placeholder="请设置密码",
            )
            confirm_password = st.text_input(
                "确认密码",
                type="password",
                key=f"{key_prefix}_register_password_confirm",
                placeholder="请再次输入密码",
            )

            if st.button(
                "📝 注册账号",
                key=f"{key_prefix}_register_btn",
                use_container_width=True,
            ):
                if not new_username:
                    st.warning("⚠️ 用户名不能为空")
                elif not new_password:
                    st.warning("⚠️ 密码不能为空")
                elif new_password != confirm_password:
                    st.warning("⚠️ 两次输入的密码不一致")
                elif new_username in user_dict:
                    st.warning("⚠️ 该用户名已被注册，请换一个")
                else:
                    user_dict[new_username] = new_password
                    save_users(user_dict)
                    st.success("✅ 注册成功！请切换到登录页面登录")

    # 底部提示
    st.markdown("---")
    st.caption("💡 首次使用请先注册账号，已有账号请直接登录")


def logout():
    """退出登录，保存数据"""
    username = st.session_state.get("logged_in_user")
    if username:
        # 保存用户数据
        from user_data_manager import save_user_data_from_session
        save_user_data_from_session(username, st.session_state)

    # 清除登录状态
    st.session_state.logged_in_user = None
    # 保留记住的用户名
    remember_me = st.session_state.get("remember_me")
    st.session_state.clear()
    if remember_me:
        st.session_state["remember_me"] = remember_me
