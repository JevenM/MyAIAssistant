import streamlit as st
import io, os
import hmac
from PIL import Image
from pydantic import BaseModel

# 本地模型: 使用 Ollama
from langchain_ollama import ChatOllama

# 云端模型: 使用 OpenAI 兼容接口 (通义/DeepSeek)
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import HumanMessage, AIMessage

# 搜索工具导入
import requests
import json

# 本地搜索: DuckDuckGo
from langchain_community.tools import DuckDuckGoSearchRun

# 云端搜索: SearchAPI
from langchain_community.utilities.searchapi import SearchApiAPIWrapper

from langchain.memory import ConversationBufferMemory

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from login import login_and_register

st.set_page_config(
    page_title="小橙子",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None


if "messages" not in st.session_state:
    st.session_state.messages = {}
    # 初始化聊天记录

if "chat_bot" not in st.session_state["messages"]:
    st.session_state["messages"]["chat_bot"] = []

if "online" not in st.session_state:
    st.session_state.online = False

# 模型配置默认值
if "model_provider" not in st.session_state:
    st.session_state.model_provider = "cloud"  # 默认使用云端模型

if "local_model_name" not in st.session_state:
    st.session_state.local_model_name = "qwen2.5:3b"

if "cloud_model_name" not in st.session_state:
    st.session_state.cloud_model_name = "deepseek-v4-flash"

if "search_provider" not in st.session_state:
    st.session_state.search_provider = "duckduckgo"

# API 配置
DASHSCOPE_API_KEY = "sk-884a7ea43d0e40adba0353f8ea21fc15"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
SEARCHAPI_API_KEY = "uMGPH1BuhRnHeurzpya6YEae"

# 免费搜索 API Keys (需要用户自己申请)
# Google Serper: https://serper.dev/ (免费 2500次/月)
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
# Tavily: https://tavily.com/ (免费 1000次/月)
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
# SerpAPI: https://serpapi.com/ (免费 100次/月)
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")


def logout():
    st.session_state.logged_in_user = None


if "logged_in_user" not in st.session_state or not st.session_state.logged_in_user:
    login_and_register()

with st.sidebar:
    if st.session_state.logged_in_user:
        with st.container():
            st.success(f"你好,{st.session_state.logged_in_user}")
            st.button("退出登录", on_click=logout)

    # 设置一个可点击打开的展开区域
    with st.expander("🤓找到我的方式"):
        image_path = r"./images/微信图片_20250803180325.jpg"
        try:
            image = Image.open(image_path)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format="JPEG")
            st.image(
                image_bytes, caption="AI毛毛小橙子的微信", use_container_width=True
            )
        except Exception as e:
            st.warning(f"图片加载失败: {e}")


def history_items():
    if "logged_in_user" not in st.session_state or not st.session_state.logged_in_user:
        st.stop()
    st.title("历史记录")
    st.write("这里展示聊天记录。")
    st.json(st.session_state.messages["chat_bot"])
    st.stop()


pages = {
    "Home": [
        st.Page("manage_account.py", title="Start Your Chat"),
    ],
    "Resources": [
        st.Page("learn.py", title="Learn about us"),
        st.Page("trial.py", title="Try it out"),
    ],
    "others": [
        st.Page(history_items, title="历史记录", icon="📜"),
        st.Page("pages/1_记账页.py", title="记账页", icon="🔥"),
        st.Page("pages/2_统计页.py", title="统计页", icon="🔥"),
        st.Page("pages/3_信息页.py", title="个人信息", icon="🔥"),
        st.Page("pages/4_检索页.py", title="文档检索", icon="🔥"),
    ],
}


pg1 = st.navigation(pages, position="sidebar")
pg1.run()


# 获取模型实例
def get_model():
    if st.session_state.model_provider == "local":
        return ChatOllama(
            model=st.session_state.local_model_name,
            streaming=True,
            temperature=0.7,
        )
    else:
        return ChatOpenAI(
            model=st.session_state.cloud_model_name,
            streaming=True,
            temperature=0.7,
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
        )


model = get_model()
memory_key = "history"


class Message(BaseModel):
    content: str
    role: str


def to_message_placeholder(messages):
    return [
        (
            AIMessage(content=message["content"])
            if message["role"] == "ai"
            else HumanMessage(content=message["content"])
        )
        for message in messages
    ]


# ========== 搜索功能实现 ==========


def safe_duckduckgo_search(query: str) -> str:
    """DuckDuckGo 搜索（免费，无需 API Key）"""
    try:
        search_tool = DuckDuckGoSearchRun()
        result = search_tool.run(query)
        if result and result.strip():
            return result
        return f"[DuckDuckGo 无结果] 未能找到关于 '{query}' 的相关信息"
    except Exception as e:
        return f"[DuckDuckGo 搜索失败] {e}"


def serper_search(query: str) -> str:
    """Google Serper 搜索（免费 2500次/月）- https://serper.dev"""
    if not SERPER_API_KEY:
        return "[Serper 未配置] 请设置环境变量 SERPER_API_KEY，免费申请: https://serper.dev"

    try:
        url = "https://google.serper.dev/search"
        payload = json.dumps({"q": query})
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=payload, timeout=10)

        if response.status_code != 200:
            return f"[Serper 错误] HTTP {response.status_code}"

        data = response.json()
        results = []

        # 提取有机搜索结果
        if "organic" in data:
            for item in data["organic"][:5]:
                results.append(
                    f"- {item.get('title', '')}\n  {item.get('snippet', '')}"
                )

        if results:
            return "\n\n".join(results)
        return f"[Serper 无结果] 未能找到关于 '{query}' 的相关信息"
    except Exception as e:
        return f"[Serper 搜索错误] {e}"


def tavily_search(query: str) -> str:
    """Tavily AI 搜索（免费 1000次/月）- https://tavily.com"""
    if not TAVILY_API_KEY:
        return "[Tavily 未配置] 请设置环境变量 TAVILY_API_KEY，免费申请: https://tavily.com"

    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
        }
        response = requests.post(url, json=payload, timeout=15)

        if response.status_code != 200:
            return f"[Tavily 错误] HTTP {response.status_code}"

        data = response.json()
        results = []

        if "results" in data:
            for item in data["results"][:5]:
                results.append(
                    f"- {item.get('title', '')}\n  {item.get('content', '')}"
                )

        if results:
            return "\n\n".join(results)
        return f"[Tavily 无结果] 未能找到关于 '{query}' 的相关信息"
    except Exception as e:
        return f"[Tavily 搜索错误] {e}"


def serpapi_search(query: str) -> str:
    """SerpAPI 搜索（免费 100次/月）- https://serpapi.com"""
    if not SERPAPI_KEY:
        return (
            "[SerpAPI 未配置] 请设置环境变量 SERPAPI_KEY，免费申请: https://serpapi.com"
        )

    try:
        from langchain_community.utilities import SerpAPIWrapper

        search = SerpAPIWrapper(serpapi_api_key=SERPAPI_KEY)
        result = search.run(query)
        if result and result.strip():
            return result
        return f"[SerpAPI 无结果] 未能找到关于 '{query}' 的相关信息"
    except ImportError:
        return "[SerpAPI 未安装] 请运行: pip install google-search-results"
    except Exception as e:
        return f"[SerpAPI 搜索错误] {e}"


def safe_searchapi_search(query: str) -> str:
    """SearchAPI 百度搜索"""
    try:
        search_wrapper = SearchApiAPIWrapper(
            engine="baidu", searchapi_api_key=SEARCHAPI_API_KEY
        )
        result = search_wrapper.run(query)
        if result and result.strip():
            return result
        return f"[百度搜索无结果] 未能找到关于 '{query}' 的相关信息"
    except Exception as e:
        return f"[百度搜索错误] {e}"


def get_search_result(query: str) -> str:
    """根据配置获取搜索结果"""
    provider = st.session_state.search_provider

    search_functions = {
        "duckduckgo": safe_duckduckgo_search,
        "serper": serper_search,
        "tavily": tavily_search,
        "serpapi": serpapi_search,
        "baidu": safe_searchapi_search,
    }

    search_func = search_functions.get(provider, safe_duckduckgo_search)
    return search_func(query)


# ========== 聊天界面布局 ==========

# 顶部配置栏 - 第一行：模型配置
config_col1, config_col2, config_col3, search_col = st.columns([1, 1, 1, 1.2])

with config_col1:
    model_provider = st.segmented_control(
        "模型来源",
        options=["local", "cloud"],
        format_func=lambda x: "🏠 本地" if x == "local" else "☁️ 云端",
        default=st.session_state.model_provider,
        key="model_provider_control",
    )
    st.session_state.model_provider = model_provider

with config_col2:
    if model_provider == "local":
        local_model = st.selectbox(
            "本地模型",
            options=["qwen2.5:7b", "qwen2.5:3b", "llama3.2", "mistral:7b"],
            index=["qwen2.5:7b", "qwen2.5:3b", "llama3.2", "mistral:7b"].index(
                st.session_state.local_model_name
            ),
            key="local_model_select",
        )
        st.session_state.local_model_name = local_model
    else:
        cloud_model = st.selectbox(
            "云端模型",
            options=["deepseek-v4-flash", "qwen-max", "qwen-plus", "qwen-turbo"],
            index=["deepseek-v4-flash", "qwen-max", "qwen-plus", "qwen-turbo"].index(
                st.session_state.cloud_model_name
            ),
            key="cloud_model_select",
        )
        st.session_state.cloud_model_name = cloud_model

with config_col3:
    # toggle 的 key 参数会自动绑定到 session_state.online
    # 点击后 session_state.online 会立即更新
    st.toggle("联网搜索", key="online")

# 第二行：搜索引擎选择（仅在联网搜索开启时显示）
# 需要在 toggle 渲染之后判断，确保获取到最新的 session_state.online 值
if st.session_state.online:
    with search_col:
        # 搜索引擎选项
        search_options = {
            "duckduckgo": "🦆 DuckDuckGo (免费无限)",
            "serper": "🔍 Google Serper (免费2500次/月)",
            "tavily": "🤖 Tavily AI (免费1000次/月)",
            "serpapi": "🔎 SerpAPI (免费100次/月)",
            "baidu": "🌐 百度搜索 (SearchAPI)",
        }
        search_provider = st.selectbox(
            "搜索引擎",
            options=list(search_options.keys()),
            format_func=lambda x: search_options[x],
            index=(
                list(search_options.keys()).index(st.session_state.search_provider)
                if st.session_state.search_provider in search_options
                else 0
            ),
            key="search_provider_select",
        )
        st.session_state.search_provider = search_provider

        # API Key 帮助提示
        if st.session_state.search_provider != "duckduckgo":
            st.caption(
                "💡 **获取免费 API Key:** "
                "[Serper](https://serper.dev) | "
                "[Tavily](https://tavily.com) | "
                "[SerpAPI](https://serpapi.com) | "
                "设置环境变量后生效"
            )
        else:
            st.caption("🦆 DuckDuckGo 完全免费，无需 API Key")

# st.divider()

# 聊天记录容器
con = st.container(key="message_con", height=480)

for message in st.session_state.messages["chat_bot"]:
    with con.chat_message(message["role"]):
        st.write(message["content"])

# 定义 LCEL Chain
search_chain = RunnableLambda(
    lambda x: {
        "context": get_search_result(x["input"]) if st.session_state.online else "",
        "input": x["input"],
        "history": to_message_placeholder(x["messages"]),
    }
)

if st.session_state.online:
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name=memory_key),
            (
                "human",
                "你是一个聪明的大语言模型，下面是我从互联网搜索的结果：{context}\n\n请基于这些信息回答这个问题\n:{input}",
            ),
        ]
    )
else:
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name=memory_key),
            ("human", "{input}"),
        ]
    )

chain = search_chain | prompt | model | StrOutputParser()

# 聊天输入
if pt := st.chat_input("您好，请问有什么可以帮助您的吗？"):
    # 重新获取模型（用户可能切换了配置）
    model = get_model()
    chain = search_chain | prompt | model | StrOutputParser()

    st.session_state.messages["chat_bot"].append(
        Message(content=pt, role="human").dict()
    )
    with con.chat_message("human"):
        st.write(pt)

    with con.chat_message("ai"):
        try:
            res = chain.stream(
                {"input": pt, "messages": st.session_state.messages["chat_bot"]},
                config={"verbose": True},
            )
            response = st.write_stream(res)
        except Exception as e:
            response = f"发生错误: {e}"
            st.error(response)
    st.session_state.messages["chat_bot"].append(
        Message(content=response, role="ai").dict()
    )
