import streamlit as st
import tempfile
import os
import chromadb
import uuid
import pandas as pd
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_community.document_loaders import TextLoader, Docx2txtLoader
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.prompts import PromptTemplate

# from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.agents import AgentExecutor
from langchain.agents.agent_toolkits import VectorStoreToolkit, VectorStoreInfo
from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from login import require_login

# 导入 GraphRAG 模块
from graphrag import (
    GraphRAGBuilder,
    GraphRAGRetriever,
    KnowledgeGraph,
    KnowledgeGraphVisualizer,
    ReasoningExplainer,
)

# 本地模型: 使用 Ollama 替代通义大模型
from langchain_ollama import ChatOllama

# 云端模型: 使用 OpenAI 兼容接口 (通义/DeepSeek)
from langchain_openai import ChatOpenAI
from langchain.tools.retriever import create_retriever_tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.agents import AgentAction, AgentFinish
from langchain.agents import BaseSingleActionAgent
from pydantic import PrivateAttr

# 设置页面配置
st.set_page_config(page_title="文档问答", layout="wide")

# ========== 统一登录检查 ==========
require_login()

st.title("📄 文档问答（GraphRAG 增强版）")

# GraphRAG 状态初始化
if "knowledge_graph" not in st.session_state:
    st.session_state.knowledge_graph = None
if "use_graphrag" not in st.session_state:
    st.session_state.use_graphrag = False  # 默认关闭
if "graph_built" not in st.session_state:
    st.session_state.graph_built = False

bot_id = "doc_bot"
col1, col2 = st.columns([0.5, 0.5])


if bot_id not in st.session_state["messages"]:
    st.session_state["messages"][bot_id] = []

# 初始化
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = {}

upload_files = col1.file_uploader(
    label="上传文本文件",
    type=["txt", "docx", "doc"],
    accept_multiple_files=True,
    key="uploader",
)

# 文件上传后只做一次分割和嵌入，缓存到 session_state
if "vectorstore_cache" not in st.session_state:
    st.session_state.vectorstore_cache = None
if "splits_cache" not in st.session_state:
    st.session_state.splits_cache = None
if "doc_stat_cache" not in st.session_state:
    st.session_state.doc_stat_cache = None


def print_info(total_length, chunk_size, chunk_overlap):
    with col1_exp:
        st.info(
            f"检测到文档总长度 {total_length} 字符，自动设置 chunk_size={chunk_size}, chunk_overlap={chunk_overlap}"
        )


# 自定义 ChromaDB 向量存储类
class CustomChromaVectorStore(VectorStore):
    def __init__(self, collection, embedding_function):
        self.collection = collection
        self.embedding_function = embedding_function

    def add_texts(
        self, texts: List[str], metadatas: Optional[List[dict]] = None, **kwargs
    ) -> List[str]:
        if metadatas is None:
            metadatas = [{}] * len(texts)
        embeddings = self.embedding_function.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in texts]
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        return ids

    def similarity_search(self, query: str, k: int = 6, **kwargs) -> List[Document]:
        query_embedding = self.embedding_function.embed_documents([query])[0]
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        print("similarity_search 被执行")
        print(f"ChromaDB查询结果: {results}")
        documents = []
        # 检查结果是否为空
        if not results.get("documents") or not results["documents"][0]:
            print("检索结果为空")
            return documents
        for i in range(len(results["documents"][0])):
            doc = Document(
                page_content=results["documents"][0][i],
                metadata=(
                    results["metadatas"][0][i]
                    if results["metadatas"] and results["metadatas"][0]
                    else {}
                ),
            )
            documents.append(doc)
        # Streamlit显示逻辑
        self._display_search_results(documents)
        return documents

    def _display_search_results(self, documents):
        """显示检索结果的独立方法"""
        try:
            # 如果传入了特定的列，使用该列，否则使用全局布局
            if col2 is not None:
                with col2.expander("检索文档"):
                    st.write(f"检索到 {len(documents)} 条文档：")
                    for i, doc in enumerate(documents):
                        st.write(f"文档 {i+1}: {doc.page_content[:200]}...")
            else:
                # fallback到全局显示
                with st.expander("检索文档1"):
                    st.write(f"检索到 {len(documents)} 条文档：")
                    for i, doc in enumerate(documents):
                        st.write(f"文档 {i+1}: {doc.page_content[:200]}...")
        except Exception as e:
            print(f"Streamlit显示出错: {e}")

    def similarity_search_with_score(
        self, query: str, k: int = 6, **kwargs
    ) -> List[Tuple[Document, float]]:
        print("similarity_search_with_score 被调用")  # 调试信息
        query_embedding = self.embedding_function.embed_documents([query])[0]
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        print(f"ChromaDB查询结果: {results}")  # 调试信息
        documents_with_scores = []

        # 检查结果是否为空
        if not results.get("documents") or not results["documents"][0]:
            print("检索结果为空")
            return documents_with_scores
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for i in range(len(results["documents"][0])):
            doc = Document(
                page_content=results["documents"][0][i],
                metadata=metadatas[i] if metadatas else {},
            )
            score = distances[i] if i < len(distances) else 0.0
            documents_with_scores.append((doc, score))
        return documents_with_scores

    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 6,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs,
    ) -> List[Document]:
        docs = self.similarity_search(query, k=fetch_k)
        return docs[:k]

    def _similarity_search_with_relevance_scores(
        self, query: str, k: int = 6, **kwargs
    ) -> List[Tuple[Document, float]]:
        print("_similarity_search_with_relevance_scores 被调用!")
        return self.similarity_search_with_score(query, k, **kwargs)

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding,
        metadatas: Optional[List[dict]] = None,
        **kwargs,
    ):
        client = chromadb.Client()
        collection = client.create_collection("documents")
        instance = cls(
            collection=collection,
            embedding_function=embedding,
        )
        instance.add_texts(texts, metadatas)
        return instance

    def search(self, query: str, search_type: str, **kwargs: Any) -> List[Document]:
        """Return docs most similar to query using specified search type."""
        print(f"search方法被调用，search_type: {search_type}")

        if search_type == "similarity":
            return self.similarity_search(query, **kwargs)
        elif search_type == "similarity_score_threshold":
            docs_scores = self.similarity_search_with_score(query, **kwargs)
            return [doc for doc, score in docs_scores]
        elif search_type == "mmr":
            return self.max_marginal_relevance_search(query, **kwargs)
        else:
            return self.similarity_search(query, **kwargs)


# 自定义 ReAct 代理类
class CustomReActAgent(BaseSingleActionAgent):
    _llm = PrivateAttr()
    _tools = PrivateAttr()
    _prompt = PrivateAttr()
    _tool_names = PrivateAttr()

    def __init__(self, llm, tools, prompt):
        super().__init__()
        self._llm = llm
        self._tools = tools
        self._prompt = prompt
        self._tool_names = [tool.name for tool in tools]

    @property
    def input_keys(self):
        return ["input"]

    def get_allowed_tools(self):
        return self._tool_names

    def plan(self, intermediate_steps, **kwargs):
        # 格式化聊天历史
        chat_history = kwargs.get("chat_history", [])
        history_str = ""
        for msg in chat_history:
            if isinstance(msg, HumanMessage):
                history_str += f"Human: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                history_str += f"Assistant: {msg.content}\n"

        # Initialize a thought for StreamlitCallbackHandler
        # with col2.expander("Agent Thought"):
        #     st.write("Starting to process the query...")
        # 强制第一次调用工具
        if not intermediate_steps:
            return AgentAction(
                tool="文档检索",
                tool_input=kwargs["input"],
                log="Thought: 需要检索文档以回答用户问题。",
            )

        # 调试：显示聊天历史
        # with col2.expander("聊天历史"):
        #     st.write(f"Chat History:\n{history_str}")

        # 格式化代理暂存区，处理空值
        agent_scratchpad = kwargs.get("agent_scratchpad", "")
        for action, observation in intermediate_steps:
            agent_scratchpad += f"Thought: {action.log}\nAction: {action.tool}\nAction Input: {action.tool_input}\nObservation: {observation}\n"

        # 准备提示词
        prompt_input = {
            "input": kwargs["input"],
            "chat_history": history_str,
            "agent_scratchpad": agent_scratchpad,
        }
        full_prompt = self._prompt.format(**prompt_input)

        # 调试：显示完整提示词
        # with col2.expander("大模型提示"):
        #     st.write(f"LLM Prompt:\n{full_prompt}")

        # 调用 LLM
        response = self._llm.invoke([SystemMessage(content=full_prompt)])
        response_text = response.content
        print(f"Raw LLM Response:\n{response_text}")
        if "Action:" not in response_text:
            print("Warning: LLM response does not contain Action field!")
        # 调试：显示 LLM 响应
        with col2.expander("大模型响应"):
            st.write(f"LLM Response:\n{response_text}")

        # 解析响应
        if "Final Answer:" in response_text:
            final_answer = response_text.split("Final Answer:")[-1].strip()
            return AgentFinish(
                return_values={"output": final_answer}, log=response_text
            )
        elif "Thought:" in response_text and "Action:" in response_text:
            lines = response_text.split("\n")
            action = None
            action_input = None
            thought = None
            for line in lines:
                if line.startswith("Thought:"):
                    thought = line.replace("Thought:", "").strip()
                elif line.startswith("Action:"):
                    action = line.replace("Action:", "").strip()
                elif line.startswith("Action Input:"):
                    action_input = line.replace("Action Input:", "").strip()

            if action and action_input and thought:
                with col2.chat_message("assistant").expander("动作规划"):
                    st.write(f"执行动作: {action}, 输入: {action_input}")
                return AgentAction(tool=action, tool_input=action_input, log=thought)
        return AgentFinish(
            return_values={"output": "抱歉，这个问题我还不知道。"},
            log="LLM 响应未遵循 ReAct 格式或未找到相关内容",
        )

    async def aplan(self, intermediate_steps, **kwargs):
        return self.plan(intermediate_steps, **kwargs)


model_path = "E:\\Doctor1\\coding\\Langchain-Chatchat\\_models\\m3e-base"


# 使用 m3e-base 模型 (支持中文效果较好)
def get_m3e_embeddings():
    return HuggingFaceEmbeddings(
        model_name=model_path,  # huggingface上的模型名称
        model_kwargs={"device": "cpu"},  # 如果有GPU可以改为 "cuda"
        encode_kwargs={"normalize_embeddings": True},  # 推荐归一化
    )


@st.cache_resource(
    ttl="30s"
)  # 30秒缓冲时间，所以30秒之内无论是切换页面还是再上传文件并不会执行这个函数，不过别急，30秒之后会自动刷新~
def configure_retriever(_uploaded_files, _reset_collection=False):
    docs = []
    print(f"传进来几个:{len(_uploaded_files)}")
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in _uploaded_files:
            temp_filepath = os.path.join(temp_dir, file.name)
            with open(temp_filepath, "wb") as f:
                f.write(file.getvalue())

            if file.name.endswith(".txt"):
                loader = TextLoader(temp_filepath, encoding="utf-8")
            elif file.name.endswith((".docx", ".doc")):
                loader = Docx2txtLoader(temp_filepath)
            else:
                st.warning(f"⚠️ 不支持的文件类型: {file.name}")
                continue
            docs.extend(loader.load())

    if not docs:
        raise ValueError("❌ 没有加载到有效文档。")

    # 根据文件总长度自适应 chunk_size
    total_length = sum(len(doc.page_content) for doc in docs)

    # 例如每1万字符 chunk_size 增加 100，最大 1500
    chunk_size = min(300 + total_length // 10000 * 100, 1500)
    chunk_overlap = int(chunk_size * 0.1)  # 10% 重叠

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    splits = text_splitter.split_documents(docs)

    embeddings = get_m3e_embeddings()
    # client = chromadb.Client()
    # 推荐: 使用 LangChain 的标准 Chroma 类，并可以指定持久化路径
    client = chromadb.PersistentClient(path="./chroma_db")  # 可选的持久化

    # 检查并删除现有集合以避免冲突
    if _reset_collection:
        try:
            client.delete_collection("all-my-documents")
        except Exception:
            pass
    collection = client.get_or_create_collection("all-my-documents")

    documents = [doc.page_content for doc in splits]
    metadatas = [doc.metadata for doc in splits]
    embeddings_list = embeddings.embed_documents(documents)
    ids = [str(uuid.uuid4()) for _ in documents]

    collection.add(
        documents=documents,
        embeddings=embeddings_list,
        metadatas=metadatas,
        ids=ids,
    )

    vectorstore = CustomChromaVectorStore(
        collection=collection, embedding_function=embeddings
    )

    print(f"Chroma Collection Size: {vectorstore.collection.count()}")

    # 测试检索器
    # test_query = "作为家中的第二个孩子"
    # results = vectorstore.similarity_search(test_query, k=2)
    # print(f"Test Query Results: {results}")

    # st.session_state.is_loaded_database = True
    return (
        vectorstore,
        splits,
        len(_uploaded_files),
        total_length,
        chunk_size,
        chunk_overlap,
    )


if not upload_files:
    # 回填展示（跨页面回来时也能看到）
    if (
        "uploaded_files" in st.session_state
        and st.session_state["uploaded_files"] != {}
    ):
        col1.write("已上传文件：")
        for file_name in st.session_state["uploaded_files"]:
            col1.write(f"📄 {file_name}")
    else:
        st.info("请先上传文件")
        st.stop()
else:
    for f in upload_files:
        # 以文件名作为 key，避免重复
        st.session_state["uploaded_files"][f.name] = f

print(st.session_state["uploaded_files"].values())
col1_exp = col1.expander("读取并分割文件")


# 调用 configure_retriever 并显示文档加载信息
if st.session_state.vectorstore_cache is None or st.session_state.splits_cache is None:
    vectorstore, splits, len_files, total_length, chunk_size, chunk_overlap = (
        configure_retriever(list(st.session_state["uploaded_files"].values()))
    )
    st.session_state.vectorstore_cache = vectorstore
    st.session_state.splits_cache = splits
    st.session_state.doc_stat_cache = (
        len_files,
        total_length,
        chunk_size,
        chunk_overlap,
    )
else:
    vectorstore = st.session_state.vectorstore_cache
    splits = st.session_state.splits_cache
    len_files, total_length, chunk_size, chunk_overlap = st.session_state.doc_stat_cache
print_info(total_length, chunk_size, chunk_overlap)
# 展示分割片段表格
df = pd.DataFrame(
    {
        "片段ID": range(1, len(splits) + 1),
        "文本内容": [doc.page_content for doc in splits],
    }
)
with col1_exp:
    st.success(f"✅ 加载了 {len_files} 个文档，分割为 {len(splits)} 个片段")
    st.dataframe(df, height=300, use_container_width=True)

# ========== GraphRAG 知识图谱构建 ==========

graph_col1, graph_col2 = col1.columns([2, 1])


# 控制知识图谱增强开关和构建按钮
with graph_col1:
    st.toggle("🧠 启用知识图谱增强", key="use_graphrag")
with graph_col2:
    build_graph_btn = st.button("🔨 构建知识图谱", use_container_width=True)

# 只有在用户主动点击构建且开启增强时才构建知识图谱
if st.session_state.use_graphrag and build_graph_btn:
    with col1.status("正在构建知识图谱...", expanded=True) as status:
        st.write("📄 提取文档内容...")
        documents = [doc.page_content for doc in splits]
        st.write("🔍 识别实体和关系...")
        graph_builder = GraphRAGBuilder()
        st.session_state.knowledge_graph = graph_builder.build_from_documents(
            documents, use_llm=False
        )
        st.session_state.graph_built = True
        st.write("✅ 知识图谱构建完成！")
        status.update(label="知识图谱构建完成", state="complete")

# 只要知识图谱已构建且增强开关开启，就允许摘要和可视化
if st.session_state.use_graphrag and st.session_state.knowledge_graph:
    with col1.expander("📊 知识图谱摘要", expanded=False):
        graph_builder = GraphRAGBuilder()
        graph_builder.graph = st.session_state.knowledge_graph
        st.markdown(graph_builder.get_graph_summary())
        # 显示部分实体
        if st.session_state.knowledge_graph.entities:
            st.markdown("### 主要实体")
            entity_df = pd.DataFrame(
                [
                    {"实体名": e.name, "类型": e.entity_type, "出现次数": e.mentions}
                    for e in sorted(
                        st.session_state.knowledge_graph.entities.values(),
                        key=lambda x: x.mentions,
                        reverse=True,
                    )[:20]
                ]
            )
            st.dataframe(entity_df, use_container_width=True, hide_index=True)
        # 显示部分关系
        if st.session_state.knowledge_graph.relations:
            st.markdown("### 主要关系")
            relation_df = pd.DataFrame(
                [
                    {"源实体": r.source, "关系": r.relation_type, "目标实体": r.target}
                    for r in st.session_state.knowledge_graph.relations[:20]
                ]
            )
            st.dataframe(relation_df, use_container_width=True, hide_index=True)

    # ========== 知识图谱可视化 ==========
    with col1.expander("🌐 知识图谱可视化", expanded=False):
        # 可视化参数独立于知识图谱构建
        if "viz_height" not in st.session_state:
            st.session_state.viz_height = 600
        if "enable_physics" not in st.session_state:
            st.session_state.enable_physics = True
        viz_col1, viz_col2 = st.columns([1, 1])
        with viz_col1:
            st.session_state.viz_height = st.slider(
                "画布高度", 400, 1000, st.session_state.viz_height, step=100
            )
        with viz_col2:
            st.session_state.enable_physics = st.checkbox(
                "启用物理引擎", value=st.session_state.enable_physics
            )

        # 生成并显示可视化（只用已构建的知识图谱，不重建）
        visualizer = KnowledgeGraphVisualizer(st.session_state.knowledge_graph)
        html_content = visualizer.generate_html_visualization(
            height=st.session_state.viz_height,
            physics=st.session_state.enable_physics,
            show_edge_labels=True,
        )
        st.components.v1.html(
            html_content, height=st.session_state.viz_height + 100, scrolling=True
        )

        # 实体详情查看
        st.markdown("---")
        st.markdown("### 🔍 实体详情查看")
        entity_names = list(st.session_state.knowledge_graph.entities.keys())
        selected_entity = st.selectbox(
            "选择实体查看详情",
            options=entity_names,
            index=0 if entity_names else None,
        )
        if selected_entity:
            explainer = ReasoningExplainer(st.session_state.knowledge_graph)
            st.markdown(explainer.explain_entity_relations(selected_entity))


if st.session_state.messages[bot_id] == [] or col1.button("清空聊天记录"):
    st.session_state["messages"][bot_id] = [
        {
            "role": "assistant",
            "content": "您好，我是文档问答助手（GraphRAG增强版），请问有什么可以帮您？",
        }
    ]

for msg in st.session_state.messages[bot_id]:
    col2.chat_message(msg["role"]).write(msg["content"])


retriever = vectorstore.as_retriever(search_kwargs={"k": 4})  # 增加 k 以提高召回率


# ========== GraphRAG 增强检索工具 ==========
def graphrag_retrieve(query: str) -> str:
    """GraphRAG 增强检索函数"""
    # 基础向量检索
    docs = retriever.get_relevant_documents(query)

    # 构建基础结果
    result = "【向量检索结果】\n"
    for i, doc in enumerate(docs):
        result += f"\n文档片段 {i+1}:\n{doc.page_content}\n"

    # 知识图谱增强
    if st.session_state.use_graphrag and st.session_state.knowledge_graph:
        result += "\n\n【知识图谱增强信息】\n"

        # 查找查询中的实体
        found_entities = []
        for entity_name in st.session_state.knowledge_graph.entities:
            if entity_name in query:
                found_entities.append(entity_name)

        if found_entities:
            result += f"识别到的实体: {', '.join(found_entities)}\n\n"

            # 获取相关实体和上下文
            for entity_name in found_entities[:3]:
                entity = st.session_state.knowledge_graph.entities.get(entity_name)
                if entity:
                    result += f"📌 {entity_name}（{entity.entity_type}）\n"

                    # 获取相关实体
                    related = st.session_state.knowledge_graph.get_related_entities(
                        entity_name
                    )
                    if related:
                        result += f"   相关实体: {', '.join(list(related)[:5])}\n"

                result += "\n"
        else:
            result += "未在查询中识别到已知实体。\n"

    return result


# 创建检索工具
tool = create_retriever_tool(
    retriever,
    "文档检索",  # 这个名字至关重要
    "此工具用于从上传的文档中检索与用户问题相关的信息。请将用户的原始问题作为输入。",
)
tools = [tool]

# result = tools[0].invoke(
#     "作为家中的第二个孩子，我出生在那个计划生育政策严格执行的年代。"
# )
# print(f"Tool Result: {result}")

print([tool.name for tool in tools])
msgs = StreamlitChatMessageHistory()

# 创建对话缓冲区内存
memory = ConversationBufferMemory(
    chat_memory=msgs,
    return_messages=True,
    memory_key="chat_history",
    output_key="output",
)

instructions = """
您是一个文档问答代理，必须严格按照以下步骤回答问题：
1. 始终首先使用 '文档检索' 工具查找相关文档。
2. 基于检索结果生成最终答案。
3. 如果检索结果为空，返回“抱歉，这个问题我还不知道。”。
4. 严格按照以下格式回复：
"""

# ReAct 风格提示词
prompt_template = """{instructions}
------
- 文档检索: 用于从上传的文档中检索与用户问题相关的信息。请将用户的原始问题作为输入。

Thought: [您的思考过程]

Action: 文档检索

Action Input: [用户问题]

Observation: [检索结果]

Thought: [基于检索结果的分析]

Final Answer: [最终回答]

-------------------

Begin!

Previous conversation history:
{chat_history}

New input: {input}
Thought: {agent_scratchpad}"""

prompt = PromptTemplate.from_template(prompt_template).partial(
    instructions=instructions,
    tool_names="文档检索",
    tools="文档检索: 用于从上传的文档中检索与用户问题相关的信息。",
)

# API 配置
DASHSCOPE_API_KEY = "sk-884a7ea43d0e40adba0353f8ea21fc15"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 模型配置 (从 session_state 获取，默认本地模型)
if "model_provider" not in st.session_state:
    st.session_state.model_provider = "local"
if "local_model_name" not in st.session_state:
    st.session_state.local_model_name = "qwen2.5:3b"
if "cloud_model_name" not in st.session_state:
    st.session_state.cloud_model_name = "deepseek-v4-flash"


# 获取模型实例
def get_llm():
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


llm = get_llm()


# 创建自定义代理
agent = CustomReActAgent(llm=llm, tools=tools, prompt=prompt)

# 创建 AgentExecutor
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True,
    handle_parsing_errors=lambda e: f"解析错误: {str(e)}",
)


user_query = st.chat_input(placeholder="请开始提问吧!")
if user_query:
    col2.chat_message("Human").write(user_query)
    st.session_state["messages"][bot_id].append(
        {"role": "Human", "content": user_query}
    )
    with col2.chat_message("assistant"):
        # 显示知识图谱增强信息
        if st.session_state.use_graphrag and st.session_state.knowledge_graph:
            with st.expander("🧠 知识图谱分析", expanded=False):
                kg_info = "识别到的实体：\n"
                found_entities = []
                for entity_name in st.session_state.knowledge_graph.entities:
                    if entity_name in user_query:
                        found_entities.append(entity_name)

                if found_entities:
                    for entity_name in found_entities[:5]:
                        entity = st.session_state.knowledge_graph.entities.get(
                            entity_name
                        )
                        if entity:
                            related = (
                                st.session_state.knowledge_graph.get_related_entities(
                                    entity_name
                                )
                            )
                            kg_info += (
                                f"\n📌 **{entity_name}** ({entity.entity_type})\n"
                            )
                            if related:
                                kg_info += f"   相关: {', '.join(list(related)[:5])}\n"
                else:
                    kg_info += "未在问题中识别到已知实体"
                st.markdown(kg_info)

            # ========== 推理路径展示 ==========
            with st.expander("🔍 检索推理路径", expanded=True):
                explainer = ReasoningExplainer(st.session_state.knowledge_graph)
                # 获取检索到的文档
                retrieved_docs = retriever.get_relevant_documents(user_query)
                st.markdown(
                    explainer.explain_retrieval(
                        user_query, retrieved_docs, found_entities
                    )
                )

        agent_container = st.container()  # Dedicated container for agent output
        st_cb = StreamlitCallbackHandler(agent_container, expand_new_thoughts=True)
        try:
            print(f"User Query: {user_query}")
            response = agent_executor.invoke(
                {"input": user_query}, {"callbacks": [st_cb]}
            )
            print(f"Agent Response: {response}")
            st.session_state.messages[bot_id].append(
                {"role": "assistant", "content": response["output"]}
            )
            st.write(response["output"])
        except Exception as e:
            error_msg = f"抱歉，处理您的问题时出现了错误: {str(e)}"
            col2.error(error_msg)
            print(f"Error during agent execution: {str(e)}")  # Debugging
st.stop()
