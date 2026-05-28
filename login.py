import hmac
import streamlit as st
import json
import os

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


def login_and_register(show_warning=True):
    # 注册流程示例
    user_dict = load_users()
    tab1, tab2 = st.tabs(["🔐 登录", "🆕 注册"])

    with tab1:
        # 如果 session_state 里有记住的用户名，就填充默认值
        default_username = st.session_state.get("remember_me", "")
        # 如果用户名被自动填充，强制清空密码输入框
        if default_username and "login_password" in st.session_state:
            st.session_state["login_password"] = ""
        username = st.text_input("用户名", key="login_username", value=default_username)
        password = st.text_input("密码", type="password", key="login_password")
        remember = st.checkbox(
            "记住我", key="remember_checkbox", value=bool(default_username)
        )
        if st.button("登录", key="login_btn"):
            # 登录按钮点击后无论成功或失败都清理密码
            try:
                if username in user_dict and hmac.compare_digest(
                    password,
                    user_dict[username],
                ):
                    show_warning = False
                    st.session_state.logged_in_user = username
                    st.success("登录成功！", icon="✅")
                    # 如果勾选记住我，就存用户名；否则清空
                    if remember:
                        st.session_state["remember_me"] = username
                    else:
                        st.session_state.pop("remember_me", None)
                    st.rerun()
                else:
                    show_warning = False
                    st.error("用户名或密码错误", icon="🚨")
            finally:
                st.session_state.pop("login_password", None)

        if show_warning and "logged_in_user" not in st.session_state:
            st.warning("请先登录后再使用本页面~", icon="⚠️")
    with tab2:
        new_username = st.text_input("注册用户名", key="register_username")
        new_password = st.text_input(
            "注册密码", type="password", key="register_password"
        )
        if st.button("注册", key="register_btn"):
            if new_username in user_dict:
                st.warning("该用户名已被注册", icon="⚠️")
            else:
                user_dict[new_username] = new_password
                save_users(user_dict)
                st.success("注册成功，请返回登录", icon="✅")
                show_warning = False
