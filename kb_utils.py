"""
知识库公共工具模块
提供统一的知识库构建、管理和可视化功能
供各页面复用
"""

import os
import tempfile
import uuid
import streamlit as st
import chromadb
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# LangChain imports
from langchain_community.document_loaders import TextLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

# 本地模块
from knowledge_base_manager import (
    KnowledgeBaseManager,
    KnowledgeBaseSerializer,
)
from graphrag import (
    GraphRAGBuilder,
    KnowledgeGraph,
    KnowledgeGraphVisualizer,
)


# ========== Embedding 模型配置 ==========
DEFAULT_MODEL_PATH = "E:\\Doctor1\\coding\\Langchain-Chatchat\\_models\\m3e-base"


@st.cache_resource
def get_embeddings(model_path: str = None):
    """获取 Embedding 模型（缓存）"""
    return HuggingFaceEmbeddings(
        model_name=model_path or DEFAULT_MODEL_PATH,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ========== 文档处理工具 ==========

def load_documents_from_files(uploaded_files) -> Tuple[List[Document], List[str]]:
    """
    从上传的文件加载文档

    Args:
        uploaded_files: Streamlit 上传的文件列表

    Returns:
        (文档列表, 错误消息列表)
    """
    docs = []
    errors = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for file in uploaded_files:
            temp_path = os.path.join(temp_dir, file.name)
            with open(temp_path, "wb") as f:
                f.write(file.getvalue())

            try:
                if file.name.endswith(".txt"):
                    loader = TextLoader(temp_path, encoding="utf-8")
                elif file.name.endswith((".docx", ".doc")):
                    loader = Docx2txtLoader(temp_path)
                else:
                    errors.append(f"不支持的文件类型: {file.name}")
                    continue
                docs.extend(loader.load())
            except Exception as e:
                errors.append(f"加载文件失败 {file.name}: {str(e)}")

    return docs, errors


def split_documents(
    docs: List[Document],
    chunk_size: int = None,
    chunk_overlap: int = None
) -> List[Document]:
    """
    分割文档

    Args:
        docs: 文档列表
        chunk_size: 分块大小（自动计算如果为None）
        chunk_overlap: 重叠大小

    Returns:
        分割后的文档列表
    """
    total_length = sum(len(doc.page_content) for doc in docs)

    if chunk_size is None:
        chunk_size = min(300 + total_length // 10000 * 100, 1500)
    if chunk_overlap is None:
        chunk_overlap = int(chunk_size * 0.1)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    return text_splitter.split_documents(docs)


# ========== 向量库构建工具 ==========

def build_vectorstore(
    kb_id: str,
    splits: List[Document],
    kb_manager: KnowledgeBaseManager,
    embeddings=None
) -> Tuple[bool, str]:
    """
    构建向量库

    Args:
        kb_id: 知识库ID
        splits: 分割后的文档列表
        kb_manager: 知识库管理器
        embeddings: Embedding模型

    Returns:
        (是否成功, 消息)
    """
    try:
        if embeddings is None:
            embeddings = get_embeddings()

        chroma_path = str(kb_manager.get_chroma_path(kb_id))
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

        return True, f"向量库构建成功，共 {len(documents)} 条记录"
    except Exception as e:
        return False, f"向量库构建失败: {str(e)}"


# ========== 知识图谱构建工具 ==========

def build_knowledge_graph(
    documents: List[str],
    use_llm: bool = False,
    llm=None,
    progress_callback=None
) -> KnowledgeGraph:
    """
    构建知识图谱

    Args:
        documents: 文档文本列表
        use_llm: 是否使用LLM增强
        llm: LLM模型
        progress_callback: 进度回调函数

    Returns:
        知识图谱对象
    """
    builder = GraphRAGBuilder(llm=llm)
    return builder.build_from_documents(
        documents,
        use_llm=use_llm,
        show_progress=progress_callback
    )


# ========== 完整的知识库创建流程 ==========

def create_knowledge_base_full(
    kb_manager: KnowledgeBaseManager,
    name: str,
    uploaded_files,
    description: str = "",
    tags: List[str] = None,
    status_callback=None
) -> Tuple[Optional[str], List[str]]:
    """
    完整的知识库创建流程（包括向量库构建）

    Args:
        kb_manager: 知识库管理器
        name: 知识库名称
        uploaded_files: 上传的文件
        description: 描述
        tags: 标签列表
        status_callback: 状态回调函数，用于显示进度

    Returns:
        (知识库ID, 错误消息列表)
    """
    errors = []

    def update_status(msg):
        if status_callback:
            status_callback(msg)

    # 1. 创建知识库记录
    update_status("📝 创建知识库记录...")
    file_infos = [{"name": f.name, "size": f.size} for f in uploaded_files]

    new_kb = kb_manager.create_kb(
        name=name,
        files=[f.name for f in uploaded_files],
        file_infos=file_infos,
        description=description,
        tags=tags or [],
    )

    # 2. 加载文档
    update_status("📄 加载文档...")
    docs, load_errors = load_documents_from_files(uploaded_files)
    errors.extend(load_errors)

    if not docs:
        errors.append("没有成功加载任何文档")
        kb_manager.delete_kb(new_kb.id)
        return None, errors

    # 3. 分割文档
    update_status("✂️ 分割文档...")
    splits = split_documents(docs)
    update_status(f"   共分割为 {len(splits)} 个片段")

    # 4. 保存文本片段
    update_status("💾 保存文本片段...")
    splits_data = KnowledgeBaseSerializer.splits_to_dict(splits)
    kb_manager.save_splits(new_kb.id, splits_data)

    # 5. 构建向量库
    update_status("🔢 构建向量库...")
    success, msg = build_vectorstore(new_kb.id, splits, kb_manager)
    if not success:
        errors.append(msg)
    else:
        update_status(f"   {msg}")

    # 6. 更新知识库统计
    kb_manager.update_kb(
        new_kb.id,
        doc_count=len(uploaded_files),
        chunk_count=len(splits),
    )

    return new_kb.id, errors


# ========== 知识图谱可视化工具 ==========

def render_graph_visualization(
    graph: KnowledgeGraph,
    height: int = 500,
    show_edge_labels: bool = True,
    enable_physics: bool = True,
    filter_types: list = None,
    use_3d: bool = False
) -> str:
    """
    渲染知识图谱可视化

    Args:
        graph: 知识图谱对象
        height: 画布高度
        show_edge_labels: 是否显示边标签
        enable_physics: 是否启用物理引擎
        filter_types: 要显示的实体类型列表，None表示显示所有
        use_3d: 是否使用3D可视化

    Returns:
        HTML字符串
    """
    visualizer = KnowledgeGraphVisualizer(graph)
    return visualizer.generate_html_visualization(
        height=height,
        physics=enable_physics,
        show_edge_labels=show_edge_labels,
        filter_types=filter_types,
        use_3d=use_3d
    )


def display_graph_stats(graph: KnowledgeGraph):
    """
    显示知识图谱统计信息

    Args:
        graph: 知识图谱对象
    """
    import streamlit as st
    import pandas as pd
    from collections import Counter

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📊 实体数量", len(graph.entities))
    with c2:
        st.metric("🔗 关系数量", len(graph.relations))
    with c3:
        # 实体类型分布
        type_counts = Counter(e.entity_type for e in graph.entities.values())
        st.metric("📋 实体类型", len(type_counts))


def display_entity_table(graph: KnowledgeGraph, max_rows: int = 50):
    """
    显示实体表格

    Args:
        graph: 知识图谱对象
        max_rows: 最大显示行数
    """
    import streamlit as st
    import pandas as pd

    entity_data = []
    for name, entity in sorted(graph.entities.items(), key=lambda x: x[1].mentions, reverse=True)[:max_rows]:
        entity_data.append({
            "名称": name,
            "类型": entity.entity_type,
            "出现次数": entity.mentions,
            "描述": entity.description[:80] + "..." if len(entity.description) > 80 else entity.description,
        })

    if entity_data:
        st.dataframe(pd.DataFrame(entity_data), hide_index=True, use_container_width=True)
    else:
        st.info("暂无实体数据")


def display_relation_table(graph: KnowledgeGraph, max_rows: int = 50):
    """
    显示关系表格

    Args:
        graph: 知识图谱对象
        max_rows: 最大显示行数
    """
    import streamlit as st
    import pandas as pd

    relation_data = []
    for r in graph.relations[:max_rows]:
        relation_data.append({
            "源实体": r.source,
            "关系": r.relation_type,
            "目标实体": r.target,
            "置信度": f"{getattr(r, 'confidence', 1.0):.2f}",
        })

    if relation_data:
        st.dataframe(pd.DataFrame(relation_data), hide_index=True, use_container_width=True)
    else:
        st.info("暂无关系数据")


# ========== 实体/关系编辑工具 ==========

def edit_entity(
    graph: KnowledgeGraph,
    entity_name: str,
    new_type: str = None,
    new_desc: str = None,
    new_mentions: int = None
) -> bool:
    """
    编辑实体

    Args:
        graph: 知识图谱对象
        entity_name: 实体名称
        new_type: 新类型
        new_desc: 新描述
        new_mentions: 新出现次数

    Returns:
        是否成功
    """
    if entity_name not in graph.entities:
        return False

    entity = graph.entities[entity_name]
    if new_type:
        entity.entity_type = new_type
    if new_desc is not None:
        entity.description = new_desc
    if new_mentions is not None:
        entity.mentions = new_mentions

    return True


def delete_entity(graph: KnowledgeGraph, entity_name: str) -> bool:
    """
    删除实体及其相关关系

    Args:
        graph: 知识图谱对象
        entity_name: 实体名称

    Returns:
        是否成功
    """
    if entity_name not in graph.entities:
        return False

    del graph.entities[entity_name]
    # 删除相关关系
    graph.relations = [
        r for r in graph.relations
        if r.source != entity_name and r.target != entity_name
    ]

    return True


def add_entity(
    graph: KnowledgeGraph,
    name: str,
    entity_type: str,
    description: str = ""
) -> bool:
    """
    添加实体

    Args:
        graph: 知识图谱对象
        name: 实体名称
        entity_type: 实体类型
        description: 描述

    Returns:
        是否成功
    """
    from graphrag import Entity

    if name in graph.entities:
        return False

    entity = Entity(
        name=name,
        entity_type=entity_type,
        description=description,
        mentions=1
    )
    graph.add_entity(entity)
    return True


def add_relation(
    graph: KnowledgeGraph,
    source: str,
    target: str,
    relation_type: str,
    confidence: float = 0.9
) -> bool:
    """
    添加关系

    Args:
        graph: 知识图谱对象
        source: 源实体
        target: 目标实体
        relation_type: 关系类型
        confidence: 置信度

    Returns:
        是否成功
    """
    from graphrag import Relation

    if source not in graph.entities or target not in graph.entities:
        return False
    if source == target:
        return False

    relation = Relation(
        source=source,
        target=target,
        relation_type=relation_type,
        confidence=confidence
    )
    graph.add_relation(relation)
    return True


# ========== 常量定义 ==========

ENTITY_TYPES = ["人物", "组织", "地点", "时间", "产品", "事件", "概念", "数值", "其他"]
RELATION_TYPES = ["属于", "包含", "负责", "位于", "开发", "使用", "提供", "合作", "关联", "导致", "依赖"]
