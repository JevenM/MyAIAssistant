import streamlit as st
from login import require_login

# ========== 页面配置 ==========
st.set_page_config(
    page_title="关于我们 - 智能助手",
    page_icon="📖",
    layout="wide",
)

# ========== 统一登录检查 ==========
require_login()

# ========== 自定义样式 ==========
st.markdown(
    """
<style>
    .about-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 2rem;
        color: white;
        margin-bottom: 2rem;
    }
    .feature-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }
    .tech-badge {
        display: inline-block;
        background: #e9ecef;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        margin: 0.2rem;
        font-size: 0.9rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ========== 页面标题 ==========
st.markdown(
    """
<div class="about-card">
    <h1 style="margin: 0; font-size: 2.5rem;">🧊 小橙子智能助手</h1>
    <p style="font-size: 1.2rem; margin-top: 0.5rem; opacity: 0.9;">您的全能智能对话伙伴</p>
</div>
""",
    unsafe_allow_html=True,
)

# ========== 项目介绍 ==========
st.markdown("## 📝 项目简介")
st.markdown("""
小橙子智能助手是一款基于大语言模型构建的智能对话应用，集成了多种先进的人工智能技术，
旨在为用户提供便捷、高效、智能的交互体验。无论是日常对话、知识问答、文档分析还是生活记账，
小橙子都能成为您的得力助手。
""")

# ========== 核心功能 ==========
st.markdown("## ✨ 核心功能")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
    <div class="feature-card">
        <h3>💬 智能对话</h3>
        <p>支持本地模型和云端模型，可根据需求灵活切换，提供流畅的对话体验。</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div class="feature-card">
        <h3>🌐 联网搜索</h3>
        <p>集成多种搜索引擎，支持实时联网获取最新信息，让回答更加准确及时。</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div class="feature-card">
        <h3>📄 文档检索</h3>
        <p>上传文档后智能分析，支持问答和内容提取，让文档阅读更高效。</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
    <div class="feature-card">
        <h3>💰 记账本</h3>
        <p>简洁实用的记账功能，支持收支分类、备注添加，轻松管理日常开支。</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div class="feature-card">
        <h3>📊 统计分析</h3>
        <p>可视化图表展示收支情况，帮助您了解消费习惯，合理规划财务。</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div class="feature-card">
        <h3>👤 个人中心</h3>
        <p>完善的用户系统，保护您的隐私数据，支持多用户独立使用。</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ========== 技术栈 ==========
st.markdown("## 🛠️ 技术栈")

st.markdown(
    """
<span class="tech-badge">Python</span>
<span class="tech-badge">Streamlit</span>
<span class="tech-badge">LangChain</span>
<span class="tech-badge">Ollama</span>
<span class="tech-badge">OpenAI API</span>
<span class="tech-badge">ChromaDB</span>
<span class="tech-badge">DuckDuckGo</span>
<span class="tech-badge">Tavily</span>
""",
    unsafe_allow_html=True,
)

# ========== 支持的模型 ==========
st.markdown("## 🤖 支持的模型")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🏠 本地模型")
    st.markdown("""
    - **Qwen2.5** (通义千问)
    - **Llama3.2** (Meta)
    - **Mistral** (Mistral AI)

    需要本地安装 [Ollama](https://ollama.ai)
    """)

with col2:
    st.markdown("### ☁️ 云端模型")
    st.markdown("""
    - **DeepSeek** (深度求索)
    - **Qwen-Max/Plus/Turbo** (通义千问)

    支持通义千问和 DeepSeek API
    """)

# ========== 使用说明 ==========
st.markdown("## 📖 使用说明")

with st.expander("🚀 快速开始", expanded=True):
    st.markdown("""
    1. **注册/登录**：首次使用需要注册账号，之后可直接登录
    2. **选择模型**：在首页选择本地模型或云端模型
    3. **开始对话**：在输入框输入问题，即可获得智能回复
    4. **联网搜索**：开启联网搜索可获取实时信息
    """)

with st.expander("🔑 API 配置"):
    st.markdown("""
    如果需要使用联网搜索功能，可以申请以下免费 API：

    | 搜索引擎 | 免费额度 | 申请地址 |
    |---------|---------|---------|
    | Serper | 2500次/月 | https://serper.dev |
    | Tavily | 1000次/月 | https://tavily.com |
    | SerpAPI | 100次/月 | https://serpapi.com |

    配置方法：设置环境变量 `SERPER_API_KEY`、`TAVILY_API_KEY` 或 `SERPAPI_KEY`
    """)

# ========== 关于作者 ==========
st.markdown("---")
st.markdown("## 👨‍💻 关于作者")

st.markdown("""
小橙子智能助手是一个持续迭代的项目，欢迎提出宝贵意见和建议！

如果觉得这个项目对你有帮助，欢迎 ⭐ Star 支持！
""")

st.markdown("### 📞 联系方式")
st.info("📧 微信扫码添加（见侧边栏「联系我」）")
