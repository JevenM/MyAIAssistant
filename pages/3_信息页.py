import streamlit as st
import json
import os
from datetime import datetime
from login import require_login
from user_data_manager import get_user_data_manager, save_user_data_from_session

# ========== 页面配置 ==========
st.set_page_config(
    page_title="个人信息 - 智能助手",
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
data_manager = get_user_data_manager()

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

# ========== 统计信息（从持久化数据获取）==========
st.markdown("### 📊 使用统计")

stats = data_manager.get_user_stats(user)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #667eea; margin: 0;">{stats['chat_messages']}</h2>
        <p style="color: #666; margin: 0;">对话消息</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #28a745; margin: 0;">{stats['income_count']}</h2>
        <p style="color: #666; margin: 0;">收入记录</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #dc3545; margin: 0;">{stats['expense_count']}</h2>
        <p style="color: #666; margin: 0;">支出记录</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="stat-card">
        <h2 style="color: #ffc107; margin: 0;">{stats['account_records']}</h2>
        <p style="color: #666; margin: 0;">记账总数</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ========== 个人资料编辑 ==========
st.markdown("### ✏️ 编辑资料")

with st.form("profile_form"):
    col1, col2 = st.columns(2)

    with col1:
        avatar_options = {
            "🧊": "冰块", "😊": "微笑", "🌟": "星星", "🦊": "狐狸",
            "🐱": "猫咪", "🐶": "小狗", "🐼": "熊猫", "🦁": "狮子",
            "🐸": "青蛙", "🦋": "蝴蝶",
        }
        selected_avatar = st.selectbox(
            "选择头像",
            options=list(avatar_options.keys()),
            index=list(avatar_options.keys()).index(user_profile.get("avatar", "🧊"))
            if user_profile.get("avatar") in avatar_options else 0,
            format_func=lambda x: f"{x} {avatar_options[x]}",
        )
        nickname = st.text_input("昵称", value=user_profile.get("nickname", user), max_chars=20)

    with col2:
        email = st.text_input("邮箱", value=user_profile.get("email", ""), placeholder="example@email.com")
        bio = st.text_area("个人简介", value=user_profile.get("bio", ""), max_chars=200, placeholder="介绍一下自己吧...", height=80)

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

# 自动保存按钮
if st.button("💾 立即保存所有数据", type="primary", use_container_width=True):
    save_user_data_from_session(user, st.session_state)
    st.success("✅ 数据已保存到本地")

st.caption("💡 提示：系统会在您退出登录时自动保存数据")

# 数据管理标签页
data_tab1, data_tab2, data_tab3 = st.tabs(["📤 导出数据", "🗑️ 清除数据", "📜 聊天历史记录"])

with data_tab1:
    st.markdown("#### 导出个人数据")

    col1, col2 = st.columns(2)

    with col1:
        # 导出聊天记录
        chat_data = data_manager.get_chat_history(user, "chat_bot")
        if chat_data:
            export_data = json.dumps(chat_data, ensure_ascii=False, indent=2)
            st.download_button(
                "📥 下载聊天记录 (JSON)",
                export_data,
                file_name=f"chat_history_{user}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.info("暂无聊天记录")

        # 导出文档问答记录
        doc_chat_data = data_manager.get_chat_history(user, "doc_bot")
        if doc_chat_data:
            export_doc_data = json.dumps(doc_chat_data, ensure_ascii=False, indent=2)
            st.download_button(
                "📥 下载文档问答记录 (JSON)",
                export_doc_data,
                file_name=f"doc_chat_history_{user}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )

    with col2:
        # 导出记账记录
        records_data = data_manager.get_account_records(user)
        if records_data:
            records_json = json.dumps(records_data, ensure_ascii=False, indent=2)
            st.download_button(
                "📥 下载记账记录 (JSON)",
                records_json,
                file_name=f"account_records_{user}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True,
            )
        else:
            st.info("暂无记账记录")

        # 导出所有数据
        all_data = data_manager.export_all_data(user)
        all_data_json = json.dumps(all_data, ensure_ascii=False, indent=2)
        st.download_button(
            "📥 下载全部数据 (JSON)",
            all_data_json,
            file_name=f"all_data_{user}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
        )

with data_tab2:
    st.markdown("#### 清除数据")
    st.warning("⚠️ 清除操作不可恢复，请谨慎操作！")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ 清除聊天记录", use_container_width=True):
            data_manager.clear_chat_history(user, "chat_bot")
            st.session_state.messages["chat_bot"] = []
            st.success("聊天记录已清除")

        if st.button("🗑️ 清除文档问答记录", use_container_width=True):
            data_manager.clear_chat_history(user, "doc_bot")
            if "doc_bot" in st.session_state.messages:
                st.session_state.messages["doc_bot"] = []
            st.success("文档问答记录已清除")

    with col2:
        if st.button("🗑️ 清除记账记录", use_container_width=True):
            data_manager.clear_account_records(user)
            if "records" in st.session_state:
                st.session_state.records[user] = []
            st.success("记账记录已清除")

        if st.button("🗑️ 清除所有数据", use_container_width=True, type="primary"):
            data_manager.clear_all_data(user)
            st.session_state.messages = {"chat_bot": [], "doc_bot": []}
            if "records" in st.session_state:
                st.session_state.records[user] = []
            st.success("所有数据已清除")

with data_tab3:
    st.markdown("#### 📜 聊天历史记录")

    chat_type = st.radio(
        "选择聊天类型",
        options=["chat_bot", "doc_bot"],
        format_func=lambda x: "💬 普通聊天" if x == "chat_bot" else "📄 文档问答",
        horizontal=True,
    )

    # 从持久化存储获取聊天记录
    chat_history = data_manager.get_chat_history(user, chat_type)

    if chat_history:
        st.caption(f"共 {len(chat_history)} 条消息")

        search_keyword = st.text_input("🔍 搜索消息", placeholder="输入关键词...")

        with st.container(height=400):
            for i, msg in enumerate(chat_history):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                if search_keyword and search_keyword.lower() not in content.lower():
                    continue

                role_icon = "👤" if role in ["Human", "human"] else "🤖"
                role_name = "用户" if role in ["Human", "human"] else "助手"

                with st.chat_message(role_name):
                    st.markdown(f"**{role_icon} {role_name}**")
                    st.write(content)
                    st.caption(f"消息 #{i + 1}")
    else:
        st.info(f"暂无{'普通聊天' if chat_type == 'chat_bot' else '文档问答'}记录")

# ========== 底部提示 ==========
st.markdown("---")
st.caption("💡 数据自动保存在本地 user_data 目录，退出登录时会自动保存")