import streamlit as st
import json
import os
from datetime import datetime
from login import require_login

# ========== 页面配置 ==========
st.set_page_config(
    page_title="个人信息 - 小橙子智能助手",
    page_icon="👤",
    layout="wide",
)

# ========== 统一登录检查 ==========
require_login()

# ========== 用户数据文件 ==========
USER_PROFILE_FILE = "user_profiles.json"


def load_user_profiles():
    """加载用户资料"""
    if not os.path.exists(USER_PROFILE_FILE):
        return {}
    with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_profiles(profiles):
    """保存用户资料"""
    with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)


# ========== 自定义样式 ==========
st.markdown("""
<style>
    .profile-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 2rem;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .avatar-placeholder {
        width: 80px;
        height: 80px;
        background: white;
        border-radius: 50%;
        margin: 0 auto 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 2.5rem;
    }
    .stat-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ========== 页面标题 ==========
user = st.session_state.logged_in_user
profiles = load_user_profiles()

# 初始化用户资料
if user not in profiles:
    profiles[user] = {
        "nickname": user,
        "email": "",
        "avatar": "🧊",
        "bio": "",
        "created_at": datetime.now().strftime("%Y-%m-%d"),
    }
    save_user_profiles(profiles)

user_profile = profiles[user]

# 头部卡片
st.markdown(f"""
<div class="profile-header">
    <div class="avatar-placeholder">{user_profile.get('avatar', '🧊')}</div>
    <h1 style="margin: 0;">{user_profile.get('nickname', user)}</h1>
    <p style="opacity: 0.8; margin-top: 0.5rem;">注册时间：{user_profile.get('created_at', '未知')}</p>
</div>
""", unsafe_allow_html=True)

# ========== 统计信息 ==========
st.markdown("### 📊 使用统计")

col1, col2, col3, col4 = st.columns(4)

# 获取统计数据
chat_count = len(st.session_state.messages.get("chat_bot", []))
records = st.session_state.records.get(user, []) if "records" in st.session_state else []
expense_count = len([r for r in records if r.get("类型") == "支出"])
income_count = len([r for r in records if r.get("类型") == "收入"])

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #667eea; margin: 0;">{chat_count}</h2>
        <p style="color: #666; margin: 0;">对话消息</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #28a745; margin: 0;">{income_count}</h2>
        <p style="color: #666; margin: 0;">收入记录</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #dc3545; margin: 0;">{expense_count}</h2>
        <p style="color: #666; margin: 0;">支出记录</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    total_records = income_count + expense_count
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #ffc107; margin: 0;">{total_records}</h2>
        <p style="color: #666; margin: 0;">记账总数</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ========== 个人资料编辑 ==========
st.markdown("### ✏️ 编辑资料")

with st.form("profile_form"):
    col1, col2 = st.columns(2)

    with col1:
        # 头像选择
        avatar_options = {
            "🧊": "冰块",
            "😊": "微笑",
            "🌟": "星星",
            "🦊": "狐狸",
            "🐱": "猫咪",
            "🐶": "小狗",
            "🐼": "熊猫",
            "🦁": "狮子",
            "🐸": "青蛙",
            "🦋": "蝴蝶",
        }
        selected_avatar = st.selectbox(
            "选择头像",
            options=list(avatar_options.keys()),
            index=list(avatar_options.keys()).index(
                user_profile.get("avatar", "🧊")
            )
            if user_profile.get("avatar") in avatar_options
            else 0,
            format_func=lambda x: f"{x} {avatar_options[x]}",
        )

        nickname = st.text_input(
            "昵称",
            value=user_profile.get("nickname", user),
            max_chars=20,
        )

    with col2:
        email = st.text_input(
            "邮箱",
            value=user_profile.get("email", ""),
            placeholder="example@email.com",
        )

        bio = st.text_area(
            "个人简介",
            value=user_profile.get("bio", ""),
            max_chars=200,
            placeholder="介绍一下自己吧...",
            height=80,
        )

    submitted = st.form_submit_button("💾 保存修改", use_container_width=True)

    if submitted:
        profiles[user]["avatar"] = selected_avatar
        profiles[user]["nickname"] = nickname
        profiles[user]["email"] = email
        profiles[user]["bio"] = bio
        save_user_profiles(profiles)
        st.success("资料保存成功！")

# ========== 账号安全 ==========
st.markdown("---")
st.markdown("### 🔐 账号安全")

USER_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

with st.expander("🔑 修改密码"):
    old_password = st.text_input("当前密码", type="password", key="old_pwd")
    new_password = st.text_input("新密码", type="password", key="new_pwd")
    confirm_password = st.text_input("确认新密码", type="password", key="confirm_pwd")

    if st.button("修改密码", key="change_pwd_btn"):
        users = load_users()

        # 使用安全的密码比较
        import hmac
        if not hmac.compare_digest(old_password, users.get(user, "")):
            st.error("当前密码错误")
        elif not new_password:
            st.error("新密码不能为空")
        elif new_password != confirm_password:
            st.error("两次输入的密码不一致")
        else:
            users[user] = new_password
            save_users(users)
            st.success("密码修改成功！请重新登录")

# ========== 数据管理 ==========
st.markdown("---")
st.markdown("### 📁 数据管理")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 导出数据")
    if st.button("📥 导出聊天记录", use_container_width=True):
        chat_data = st.session_state.messages.get("chat_bot", [])
        if chat_data:
            export_data = json.dumps(chat_data, ensure_ascii=False, indent=2)
            st.download_button(
                "下载聊天记录 (JSON)",
                export_data,
                file_name=f"chat_history_{user}.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.info("暂无聊天记录")

with col2:
    st.markdown("#### 清除数据")
    if st.button("🗑️ 清除聊天记录", use_container_width=True):
        st.session_state.messages["chat_bot"] = []
        st.success("聊天记录已清除")

# ========== 底部提示 ==========
st.markdown("---")
st.caption("💡 如有问题或建议，欢迎通过侧边栏的联系方式反馈！")
