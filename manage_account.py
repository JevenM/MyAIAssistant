"""
开始聊天页面 - 智能对话功能
"""

import streamlit as st
import os
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

from langchain_core.runnables import RunnableLambda
from login import require_login
from user_data_manager import get_user_data_manager

# ========== 页面配置 ==========
st.set_page_config(
    page_title="开始聊天 - 智能助手",
    page_icon="💬",
    layout="wide",
)

# ========== 统一登录检查 ==========
require_login()

# ========== API 配置 ==========
DASHSCOPE_API_KEY = "sk-884a7ea43d0e40adba0353f8ea21fc15"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
SEARCHAPI_API_KEY = "uMGPH1BuhRnHeurzpya6YEae"

# 免费搜索 API Keys
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# ========== 自定义样式 ==========
st.markdown(
    """
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 560;
        background: linear-gradient(120deg, #ff6b6b, #feca57, #48dbfb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-title {
        font-size: 1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ========== 模型相关函数 ==========
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


def get_thinking_model():
    """获取支持思考过程的模型（DeepSeek Reasoner）"""
    return ChatOpenAI(
        model="deepseek-reasoner",
        streaming=True,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
    )


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
    """Google Serper 搜索（免费 2500次/月）"""
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
    """Tavily AI 搜索（免费 1000次/月）"""
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
    """SerpAPI 搜索（免费 100次/月）"""
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
    """百度搜索"""
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


# ========== 页面标题 ==========
st.markdown('<div class="main-title">🧊 智能助手</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">智能对话 · 联网搜索</div>',
    unsafe_allow_html=True,
)

# ========== 配置区域 ==========
with st.container():

    # 第一行：模型配置
    col1, col2, col3, col4, col5 = st.columns([1.3, 1.3, 0.8, 0.8, 1.3])

    with col1:
        model_provider = st.segmented_control(
            "🤖 模型来源",
            options=["local", "cloud"],
            format_func=lambda x: "🏠 本地" if x == "local" else "☁️ 云端",
            default=st.session_state.model_provider,
            key="model_provider_control",
        )
        # 检测变化并触发rerun
        if model_provider != st.session_state.model_provider:
            st.session_state.model_provider = model_provider
            st.rerun()

    with col2:
        if st.session_state.model_provider == "local":
            local_model = st.selectbox(
                "📦 本地模型",
                options=["qwen2.5:7b", "qwen2.5:3b", "llama3.2", "mistral:7b"],
                index=["qwen2.5:7b", "qwen2.5:3b", "llama3.2", "mistral:7b"].index(
                    st.session_state.local_model_name
                ),
                key="local_model_select",
            )
            if local_model != st.session_state.local_model_name:
                st.session_state.local_model_name = local_model
                st.rerun()
        else:
            cloud_model = st.selectbox(
                "☁️ 云端模型",
                options=[
                    "deepseek-v4-flash",
                    # "deepseek-reasoner",
                    "qwen3.6-plus",
                    "qwen3.6-35b-a3b",
                    # "qwen-turbo",
                ],
                index=(
                    [
                        "deepseek-v4-flash",
                        # "deepseek-reasoner",
                        "qwen3.6-plus",
                        "qwen3.6-35b-a3b",
                        # "qwen-turbo",
                    ].index(st.session_state.cloud_model_name)
                    if st.session_state.cloud_model_name
                    in [
                        "deepseek-v4-flash",
                        # "deepseek-reasoner",
                        "qwen3.6-plus",
                        "qwen3.6-35b-a3b",
                        # "qwen-turbo",
                    ]
                    else 0
                ),
                key="cloud_model_select",
            )
            if cloud_model != st.session_state.cloud_model_name:
                st.session_state.cloud_model_name = cloud_model
                st.rerun()

    with col3:
        st.toggle("🌐 联网搜索", key="online")

    with col4:
        # 思考模式开关（仅云端模型可用）
        if st.session_state.model_provider == "cloud":
            st.toggle("🧠 思考", key="show_thinking")
        else:
            st.session_state.show_thinking = False

    with col5:
        # 搜索引擎选择（仅在联网时显示）
        if st.session_state.online:
            search_options = {
                "duckduckgo": "🦆 DuckDuckGo",
                "serper": "🔍 Google",
                "tavily": "🤖 Tavily",
                "serpapi": "🔎 SerpAPI",
                "baidu": "🌐 百度",
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

        # 搜索引擎提示
        if st.session_state.online and st.session_state.search_provider != "duckduckgo":
            st.caption(
                "💡 获取免费密钥: [Serper](https://serper.dev) | "
                "[Tavily](https://tavily.com) | [SerpAPI](https://serpapi.com)"
            )

# ========== 聊天记录容器 ==========
con = st.container(key="message_con", height=450)

for message in st.session_state.messages["chat_bot"]:
    with con.chat_message(message["role"]):
        st.write(message["content"])

# ========== LCEL Chain 定义 ==========
model = get_model()
memory_key = "history"

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
                "你是一个聪明的大语言模型，下面是我从互联网搜索的结果：{context}\n\n请基于这些信息回答这个问题：{input}",
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

# ========== 聊天输入处理 ==========
user = st.session_state.logged_in_user
data_manager = get_user_data_manager()

if pt := st.chat_input("请输入您的问题..."):
    model = get_model()
    chain = search_chain | prompt | model | StrOutputParser()

    st.session_state.messages["chat_bot"].append(
        Message(content=pt, role="human").model_dump()
    )
    # 保存到持久化存储
    data_manager.save_chat_history(
        user, st.session_state.messages["chat_bot"], "chat_bot"
    )

    with con.chat_message("human"):
        st.write(pt)

    with con.chat_message("ai"):
        # 思考过程显示区域
        thinking_placeholder = None
        if st.session_state.show_thinking:
            thinking_expander = st.expander("🧠 思考过程", expanded=True)
            thinking_placeholder = thinking_expander.empty()
            thinking_placeholder.markdown("*正在思考中...*")

        try:
            # 如果开启思考模式，使用特殊处理
            if (
                st.session_state.show_thinking
                and st.session_state.model_provider == "cloud"
            ):
                thinking_model = get_thinking_model()

                thinking_prompt = ChatPromptTemplate.from_messages(
                    [
                        MessagesPlaceholder(variable_name=memory_key),
                        (
                            "human",
                            """请先思考如何回答这个问题，然后给出最终答案。

思考步骤：
1. 分析问题的核心是什么
2. 考虑需要哪些知识或信息
3. 推理得出结论
4. 组织语言给出答案

问题：{input}

请按以下格式回答：
【思考】
（这里写你的思考过程）

【回答】
（这里写最终答案）""",
                        ),
                    ]
                )

                if st.session_state.online:
                    search_context = get_search_result(pt)
                    thinking_prompt = ChatPromptTemplate.from_messages(
                        [
                            MessagesPlaceholder(variable_name=memory_key),
                            (
                                "human",
                                """我搜索到了以下信息：
{context}

请先思考如何回答这个问题，然后给出最终答案。

思考步骤：
1. 分析问题的核心是什么
2. 评估搜索结果的相关性
3. 结合搜索结果进行推理
4. 组织语言给出答案

问题：{input}

请按以下格式回答：
【思考】
（这里写你的思考过程）

【回答】
（这里写最终答案）""",
                            ),
                        ]
                    )
                    search_chain_thinking = RunnableLambda(
                        lambda x: {
                            "context": search_context,
                            "input": x["input"],
                            "history": to_message_placeholder(x["messages"]),
                        }
                    )
                    thinking_chain = (
                        search_chain_thinking
                        | thinking_prompt
                        | thinking_model
                        | StrOutputParser()
                    )
                else:
                    thinking_chain = (
                        thinking_prompt | thinking_model | StrOutputParser()
                    )

                # 流式输出
                full_response = ""
                in_thinking = False
                in_answer = False

                res = thinking_chain.stream(
                    {"input": pt, "messages": st.session_state.messages["chat_bot"]},
                )

                for chunk in res:
                    full_response += chunk

                    if "【思考】" in full_response:
                        in_thinking = True
                        in_answer = False
                    if "【回答】" in full_response:
                        in_thinking = False
                        in_answer = True

                    if in_thinking and "【思考】" in full_response:
                        thinking_content = full_response.split("【思考】")[-1]
                        if "【回答】" in thinking_content:
                            thinking_content = thinking_content.split("【回答】")[0]
                        if thinking_placeholder:
                            thinking_placeholder.markdown(thinking_content.strip())

                # 提取最终回答
                if "【回答】" in full_response:
                    answer_content = full_response.split("【回答】")[-1].strip()
                else:
                    answer_content = full_response

                st.markdown(answer_content)
                response = answer_content

            else:
                # 普通模式
                res = chain.stream(
                    {"input": pt, "messages": st.session_state.messages["chat_bot"]},
                    config={"verbose": True},
                )
                response = st.write_stream(res)

        except Exception as e:
            response = f"发生错误: {e}"
            st.error(response)

    st.session_state.messages["chat_bot"].append(
        Message(content=response, role="ai").model_dump()
    )
    # 保存到持久化存储
    data_manager.save_chat_history(
        user, st.session_state.messages["chat_bot"], "chat_bot"
    )
