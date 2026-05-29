"""
文档检索页面 - GraphRAG增强版
支持多知识库选择、合并检索、知识图谱可视化
"""

import streamlit as st
import chromadb
import uuid
import tempfile
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from langchain_community.document_loaders import TextLoader, Docx2txtLoader
from langchain_core.prompts import PromptTemplate
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.agents import AgentExecutor
from langchain_core.vectorstores import VectorStore
from langchain_core.documents import Document
from login import require_login

# 公共工具模块
from kb_utils import (
    KnowledgeBaseManager,
    KnowledgeBaseSerializer,
    get_embeddings,
)
from graphrag import GraphRAGBuilder, KnowledgeGraphVisualizer
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.tools.retriever import create_retriever_tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.agents import AgentAction, AgentFinish
from langchain.agents import BaseSingleActionAgent
from pydantic import PrivateAttr

# ========== 页面配置 ==========
st.set_page_config(page_title="文档问答", layout="wide")
require_login()

st.markdown(
    f"""<h3 align="center"> 📄 文档问答（GraphRAG 增强版）</h3>""",
    unsafe_allow_html=True,
)

# ========== 初始化 ==========
if "kb_manager" not in st.session_state:
    st.session_state.kb_manager = KnowledgeBaseManager()

kb_manager = st.session_state.kb_manager

# 状态初始化
for key, default in [
    ("selected_kb_ids", []),
    ("knowledge_graph", None),
    ("use_graphrag", False),
    ("use_llm_extract", False),
    ("current_vectorstore", None),
    ("current_splits", []),
    ("uploaded_files", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

bot_id = "doc_bot"
col1, col2 = st.columns([0.4, 0.6])

if bot_id not in st.session_state["messages"]:
    st.session_state["messages"][bot_id] = []

# ========== Embedding 配置 ==========
MODEL_PATH = "E:\\Doctor1\\coding\\Langchain-Chatchat\\_models\\m3e-base"


@st.cache_resource
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=MODEL_PATH,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ========== 自定义向量存储类 ==========
class CustomChromaVectorStore(VectorStore):
    def __init__(self, collection, embedding_function, kb_name=""):
        self.collection = collection
        self.embedding_function = embedding_function
        self.kb_name = kb_name

    def add_texts(
        self, texts: List[str], metadatas: Optional[List[dict]] = None, **kwargs
    ) -> List[str]:
        if metadatas is None:
            metadatas = [{}] * len(texts)
        embeddings = self.embedding_function.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in texts]
        self.collection.add(
            documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids
        )
        return ids

    def similarity_search(self, query: str, k: int = 6, **kwargs) -> List[Document]:
        query_embedding = self.embedding_function.embed_documents([query])[0]
        results = self.collection.query(query_embeddings=[query_embedding], n_results=k)
        if not results.get("documents") or not results["documents"][0]:
            return []
        return [
            Document(
                page_content=results["documents"][0][i],
                metadata=(
                    results["metadatas"][0][i]
                    if results["metadatas"] and results["metadatas"][0]
                    else {}
                ),
            )
            for i in range(len(results["documents"][0]))
        ]

    def search(self, query: str, search_type: str, **kwargs) -> List[Document]:
        return self.similarity_search(query, **kwargs)

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
        instance = cls(collection=collection, embedding_function=embedding)
        instance.add_texts(texts, metadatas)
        return instance


# ========== 合并检索器 ==========
class MultiVectorStoreRetriever:
    """多知识库合并检索器"""

    def __init__(self, vectorstores: List, knowledge_graph=None):
        self.vectorstores = vectorstores
        self.knowledge_graph = knowledge_graph

    def as_retriever(self, search_kwargs=None):
        return self

    def get_relevant_documents(self, query: str, k: int = 4) -> List[Document]:
        all_docs = []
        seen = set()
        for vs in self.vectorstores:
            try:
                docs = vs.similarity_search(query, k=k)
                for doc in docs:
                    h = hash(doc.page_content[:100])
                    if h not in seen:
                        seen.add(h)
                        all_docs.append(doc)
            except Exception:
                pass
        return all_docs[: k * 2]

    def invoke(self, query: str) -> List[Document]:
        return self.get_relevant_documents(query)


# ========== 简化的ReAct代理 ==========
class SimpleReActAgent(BaseSingleActionAgent):
    _llm = PrivateAttr()
    _retriever = PrivateAttr()

    def __init__(self, llm, retriever):
        super().__init__()
        self._llm = llm
        self._retriever = retriever

    @property
    def input_keys(self):
        return ["input"]

    def get_allowed_tools(self):
        return ["文档检索"]

    def plan(self, intermediate_steps, **kwargs):
        # 第一次调用时直接检索文档
        if not intermediate_steps:
            return AgentAction(
                tool="文档检索", tool_input=kwargs["input"], log="检索相关文档"
            )

        # 已有检索结果，让LLM生成答案
        docs = intermediate_steps[-1][1] if intermediate_steps else []
        docs_text = "\n\n".join(
            [f"【文档{i+1}】{doc.page_content[:500]}" for i, doc in enumerate(docs[:4])]
        )

        prompt = f"""基于以下文档内容回答用户问题。如果文档中没有相关信息，请诚实说明。

文档内容：
{docs_text}

用户问题：{kwargs["input"]}

请直接给出答案，不要添加多余的解释。"""

        response = self._llm.invoke([SystemMessage(content=prompt)])
        return AgentFinish(
            return_values={"output": response.content}, log=response.content
        )

    async def aplan(self, intermediate_steps, **kwargs):
        return self.plan(intermediate_steps, **kwargs)


# ========== 知识库加载函数 ==========
def load_knowledge_base(kb_id: str):
    """加载单个知识库"""
    kb = kb_manager.get_kb(kb_id)
    if not kb:
        return None

    embeddings = get_embeddings()

    # 加载向量存储
    if kb_manager.has_chroma_data(kb_id):
        try:
            chroma_path = str(kb_manager.get_chroma_path(kb_id))
            client = chromadb.PersistentClient(path=chroma_path)
            collection = client.get_or_create_collection("all-my-documents")
            vectorstore = CustomChromaVectorStore(
                collection=collection, embedding_function=embeddings, kb_name=kb.name
            )
        except Exception:
            return None
    else:
        return None

    # 加载文本片段
    splits_data = kb_manager.load_splits(kb_id)
    splits = KnowledgeBaseSerializer.dict_to_splits(splits_data) if splits_data else []

    # 加载知识图谱
    graph_data = kb_manager.load_graph(kb_id)
    graph = KnowledgeBaseSerializer.dict_to_graph(graph_data) if graph_data else None

    return {"kb": kb, "vectorstore": vectorstore, "splits": splits, "graph": graph}


# ========== 主界面：知识库选择 ==========
with col1:
    st.markdown("#### 📚 知识库选择")

    existing_kbs = kb_manager.list_kbs(enabled_only=True)

    if existing_kbs:
        selected_ids = []
        for kb in existing_kbs:
            has_data = kb_manager.has_chroma_data(kb.id) or kb_manager.has_graph_data(
                kb.id
            )
            icon = "✅" if has_data else "⚠️"
            label = f"{icon} {kb.name} ({kb.chunk_count}片段/{kb.entity_count}实体)"
            if st.checkbox(label, key=f"kb_sel_{kb.id}"):
                selected_ids.append(kb.id)

        # 检测选择变化，触发重新加载
        if set(selected_ids) != set(st.session_state.selected_kb_ids):
            st.session_state.selected_kb_ids = selected_ids
            st.session_state.current_vectorstore = None  # 清除缓存
            st.session_state.current_splits = []
            st.rerun()

        if selected_ids:
            total_chunks = sum(
                kb_manager.get_kb(kid).chunk_count
                for kid in selected_ids
                if kb_manager.get_kb(kid)
            )
            st.success(f"已选择 {len(selected_ids)} 个知识库，共 {total_chunks} 片段")
    else:
        st.info("暂无知识库，请上传文件创建")
        selected_ids = []

    st.divider()

    # ========== 文件上传 ==========
    st.markdown("### 📤 上传新文件")
    upload_files = st.file_uploader(
        label="上传文件创建知识库",
        type=["txt", "docx", "doc"],
        accept_multiple_files=True,
        key="uploader",
    )

    if upload_files:
        st.info(f"已选择 {len(upload_files)} 个文件")

# ========== 加载知识库数据 ==========
retriever = None
knowledge_graph = None

if st.session_state.selected_kb_ids:
    # 使用缓存避免重复加载
    if st.session_state.current_vectorstore is None:
        vectorstores = []
        all_splits = []
        all_graphs = []

        for kb_id in st.session_state.selected_kb_ids:
            data = load_knowledge_base(kb_id)
            if data:
                vectorstores.append(data["vectorstore"])
                all_splits.extend(data["splits"])
                if data["graph"]:
                    all_graphs.append(data["graph"])

        if vectorstores:
            st.session_state.current_vectorstore = vectorstores
            st.session_state.current_splits = all_splits
            st.session_state.knowledge_graph = (
                KnowledgeBaseSerializer.merge_graphs(all_graphs) if all_graphs else None
            )

    # 创建检索器
    if st.session_state.current_vectorstore:
        retriever = MultiVectorStoreRetriever(
            st.session_state.current_vectorstore, st.session_state.knowledge_graph
        )
        knowledge_graph = st.session_state.knowledge_graph

# ========== 处理新上传文件 ==========
elif upload_files and "processing_upload" not in st.session_state:
    st.session_state.processing_upload = True

    with col1.status("处理文件中...", expanded=True) as status:
        st.write("📝 创建知识库...")

        kb_name = f"知识库_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_infos = [{"name": f.name, "size": f.size} for f in upload_files]

        new_kb = kb_manager.create_kb(
            name=kb_name,
            files=[f.name for f in upload_files],
            file_infos=file_infos,
            description=f"由 {len(upload_files)} 个文件创建",
        )

        st.write("📄 处理文档...")
        docs = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for file in upload_files:
                temp_path = os.path.join(temp_dir, file.name)
                with open(temp_path, "wb") as f:
                    f.write(file.getvalue())
                if file.name.endswith(".txt"):
                    loader = TextLoader(temp_path, encoding="utf-8")
                elif file.name.endswith((".docx", ".doc")):
                    loader = Docx2txtLoader(temp_path)
                else:
                    continue
                docs.extend(loader.load())

        if docs:
            total_length = sum(len(doc.page_content) for doc in docs)
            chunk_size = min(300 + total_length // 10000 * 100, 1500)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=int(chunk_size * 0.1)
            )
            splits = text_splitter.split_documents(docs)

            embeddings = get_embeddings()
            chroma_path = str(kb_manager.get_chroma_path(new_kb.id))
            client = chromadb.PersistentClient(path=chroma_path)
            try:
                client.delete_collection("all-my-documents")
            except:
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
                collection=collection, embedding_function=embeddings, kb_name=kb_name
            )

            splits_data = KnowledgeBaseSerializer.splits_to_dict(splits)
            kb_manager.save_splits(new_kb.id, splits_data)
            kb_manager.update_kb(
                new_kb.id, doc_count=len(upload_files), chunk_count=len(splits)
            )

            st.session_state.selected_kb_ids = [new_kb.id]
            st.session_state.current_vectorstore = [vectorstore]
            st.session_state.current_splits = splits

            status.update(label="✅ 处理完成", state="complete")

        del st.session_state.processing_upload
        st.rerun()

# ========== 知识图谱控制 ==========
if retriever:
    with col1:
        st.divider()
        st.markdown("### 🧠 知识图谱")

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.toggle(
                "启用增强",
                key="use_graphrag",
                help="启用GraphRAG知识图谱增强检索，可以在回答问题时利用实体关系图谱提供更准确的上下文"
            )
        with c2:
            st.toggle(
                "LLM抽取",
                key="use_llm_extract",
                help="使用大语言模型进行实体和关系抽取（比规则抽取更精确但速度较慢）"
            )
        with c3:
            build_btn = st.button("打开启动增强构建图谱", use_container_width=True)

        if (
            st.session_state.use_graphrag
            and build_btn
            and st.session_state.current_splits
        ):
            with st.status("构建知识图谱...", expanded=True) as status:
                documents = [
                    doc.page_content for doc in st.session_state.current_splits
                ]

                llm = None
                if st.session_state.use_llm_extract:
                    if st.session_state.get("model_provider") == "local":
                        llm = ChatOllama(
                            model=st.session_state.get(
                                "local_model_name", "qwen2.5:3b"
                            ),
                            temperature=0.3,
                        )
                    else:
                        llm = ChatOpenAI(
                            model=st.session_state.get(
                                "cloud_model_name", "deepseek-v4-flash"
                            ),
                            temperature=0.3,
                            api_key="sk-884a7ea43d0e40adba0353f8ea21fc15",
                            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                        )

                graph_builder = GraphRAGBuilder(llm=llm)
                knowledge_graph = graph_builder.build_from_documents(
                    documents, use_llm=st.session_state.use_llm_extract
                )
                st.session_state.knowledge_graph = knowledge_graph

                if st.session_state.selected_kb_ids:
                    graph_data = KnowledgeBaseSerializer.graph_to_dict(knowledge_graph)
                    kb_manager.save_graph(
                        st.session_state.selected_kb_ids[0], graph_data
                    )

                status.update(label="✅ 构建完成", state="complete")

        # 知识图谱摘要和可视化
        if st.session_state.use_graphrag and knowledge_graph:
            with st.expander("📊 知识图谱摘要"):
                graph_builder = GraphRAGBuilder()
                graph_builder.graph = knowledge_graph
                st.markdown(graph_builder.get_graph_summary())

            with st.expander("🌐 知识图谱可视化"):
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    viz_height = st.slider("高度", 400, 800, 500)
                with c2:
                    show_edge_labels = st.checkbox(
                        "显示关系标签",
                        True,
                        key="rg_show_labels",
                        help="在图谱连线上显示关系的类型文字（如'属于'、'包含'等）"
                    )
                with c3:
                    use_3d_rg = st.toggle(
                        "🌐 3D视图",
                        value=False,
                        key="rg_use_3d",
                        help="切换到3D球状视图，可以更直观地观察实体间的空间关系"
                    )

                visualizer = KnowledgeGraphVisualizer(knowledge_graph)
                html = visualizer.generate_html_visualization(
                    height=viz_height, physics=True, show_edge_labels=show_edge_labels, use_3d=use_3d_rg
                )
                st.components.v1.html(html, height=viz_height + 50)
                if use_3d_rg:
                    st.caption("💡 3D视图：左键旋转，右键平移，滚轮缩放，点击节点查看详情")
                else:
                    st.caption("💡 拖拽调整位置，滚轮缩放，双击节点查看详情")

# ========== 聊天界面 ==========
if not retriever:
    with col2:
        st.info("👈 请选择知识库或上传文件")
    st.stop()

# 初始化聊天
if not st.session_state.messages[bot_id]:
    st.session_state.messages[bot_id] = [
        {"role": "assistant", "content": "您好，我是文档问答助手，请问有什么可以帮您？"}
    ]

# if col2.button("🗑️ 清空对话"):
#     st.session_state.messages[bot_id] = [
#         {"role": "assistant", "content": "您好，我是文档问答助手，请问有什么可以帮您？"}
#     ]

# 显示历史消息
for msg in st.session_state.messages[bot_id]:
    col2.chat_message(msg["role"]).write(msg["content"])

# ========== 模型配置 ==========
DASHSCOPE_API_KEY = "sk-884a7ea43d0e40adba0353f8ea21fc15"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def get_llm():
    provider = st.session_state.get("model_provider", "local")
    if provider == "local":
        return ChatOllama(
            model=st.session_state.get("local_model_name", "qwen2.5:3b"),
            temperature=0.7,
        )
    return ChatOpenAI(
        model=st.session_state.get("cloud_model_name", "deepseek-v4-flash"),
        temperature=0.7,
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
    )


# 创建代理
llm = get_llm()
agent = SimpleReActAgent(llm=llm, retriever=retriever)

msgs = StreamlitChatMessageHistory()
memory = ConversationBufferMemory(
    chat_memory=msgs,
    return_messages=True,
    memory_key="chat_history",
    output_key="output",
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=[create_retriever_tool(retriever, "文档检索", "检索相关文档")],
    memory=memory,
    verbose=False,  # 关闭详细日志
    handle_parsing_errors=lambda e: f"解析错误: {e}",
    max_iterations=2,  # 限制迭代次数，避免重复检索
)

# ========== 处理用户输入 ==========
user_query = st.chat_input(placeholder="请输入问题...")

if user_query:
    col2.chat_message("Human").write(user_query)
    st.session_state.messages[bot_id].append({"role": "Human", "content": user_query})

    with col2.chat_message("assistant"):
        # 显示知识图谱分析
        if st.session_state.use_graphrag and knowledge_graph:
            found_entities = [
                name for name in knowledge_graph.entities if name in user_query
            ][:5]
            if found_entities:
                with st.expander("🧠 识别到的实体"):
                    for entity_name in found_entities:
                        entity = knowledge_graph.entities.get(entity_name)
                        if entity:
                            related = list(
                                knowledge_graph.get_related_entities(entity_name)
                            )[:5]
                            st.write(f"📌 **{entity_name}** ({entity.entity_type})")
                            if related:
                                st.write(f"   相关: {', '.join(related)}")

        # 执行问答（不使用StreamlitCallbackHandler避免错误）
        try:
            # 先检索文档
            with st.spinner("检索中..."):
                docs = retriever.get_relevant_documents(user_query, k=4)

            if docs:
                # 构建提示词
                docs_text = "\n\n".join(
                    [
                        f"【文档{i+1}】{doc.page_content[:500]}"
                        for i, doc in enumerate(docs)
                    ]
                )

                prompt = f"""基于以下文档内容回答用户问题。

文档内容：
{docs_text}

用户问题：{user_query}

请基于文档内容给出准确、简洁的回答。如果文档中没有相关信息，请诚实说明。"""

                response = llm.invoke([SystemMessage(content=prompt)])
                answer = response.content
            else:
                answer = "抱歉，未找到相关文档内容。"

            st.write(answer)
            st.session_state.messages[bot_id].append(
                {"role": "assistant", "content": answer}
            )

        except Exception as e:
            error_msg = f"处理出错: {str(e)}"
            st.error(error_msg)
            st.session_state.messages[bot_id].append(
                {"role": "assistant", "content": error_msg}
            )

st.stop()
