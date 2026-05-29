"""
知识库管理模块
实现知识库的创建、加载、保存、删除等管理功能
支持向量库、知识图谱、文本片段的本地化存储与复用
支持多知识库合并检索
"""

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class FileInfo:
    """文件信息数据类"""
    name: str  # 文件名
    size: int = 0  # 文件大小（字节）
    path: str = ""  # 原始路径（如果有）

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "FileInfo":
        return cls(**data)


@dataclass
class KnowledgeBase:
    """知识库数据类"""

    id: str  # 知识库唯一ID
    name: str  # 知识库名称
    files: List[str] = field(default_factory=list)  # 来源文件名列表
    file_infos: List[Dict] = field(default_factory=list)  # 详细文件信息
    created_at: str = ""  # 创建时间
    updated_at: str = ""  # 更新时间
    enabled: bool = True  # 是否启用
    description: str = ""  # 描述
    doc_count: int = 0  # 文档数量
    chunk_count: int = 0  # 片段数量
    entity_count: int = 0  # 实体数量
    relation_count: int = 0  # 关系数量
    tags: List[str] = field(default_factory=list)  # 标签

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeBase":
        """从字典创建"""
        # 兼容旧版本数据
        if "file_infos" not in data:
            data["file_infos"] = []
        if "tags" not in data:
            data["tags"] = []
        return cls(**data)

    def get_file_summary(self) -> str:
        """获取文件摘要信息"""
        if not self.files:
            return "无文件"
        if len(self.files) <= 3:
            return ", ".join(self.files)
        return f"{', '.join(self.files[:3])} 等{len(self.files)}个文件"


class KnowledgeBaseManager:
    """知识库管理器"""

    # 默认存储根目录
    DEFAULT_ROOT = "./knowledge_bases"

    # 索引文件名
    INDEX_FILE = "knowledge_index.json"

    def __init__(self, root_path: str = None):
        """
        初始化知识库管理器

        Args:
            root_path: 知识库存储根目录，默认为 ./knowledge_bases
        """
        self.root_path = Path(root_path or self.DEFAULT_ROOT)
        self.index_path = self.root_path / self.INDEX_FILE
        self._ensure_root_dir()
        self._index: Dict[str, KnowledgeBase] = self._load_index()

    def _ensure_root_dir(self):
        """确保根目录存在"""
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict[str, KnowledgeBase]:
        """加载知识库索引"""
        if not self.index_path.exists():
            return {}

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {kb_id: KnowledgeBase.from_dict(kb_data) for kb_id, kb_data in data.items()}
        except Exception as e:
            print(f"加载知识库索引失败: {e}")
            return {}

    def _save_index(self):
        """保存知识库索引"""
        try:
            data = {kb_id: kb.to_dict() for kb_id, kb in self._index.items()}
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存知识库索引失败: {e}")

    def generate_kb_id(self) -> str:
        """生成唯一知识库ID"""
        return f"kb_{uuid.uuid4().hex[:12]}"

    def get_kb_path(self, kb_id: str) -> Path:
        """获取知识库目录路径"""
        return self.root_path / kb_id

    def create_kb(
        self,
        name: str,
        files: List[str] = None,
        file_infos: List[Dict] = None,
        description: str = "",
        tags: List[str] = None,
        kb_id: str = None,
    ) -> KnowledgeBase:
        """
        创建新知识库

        Args:
            name: 知识库名称
            files: 来源文件名列表
            file_infos: 详细文件信息列表
            description: 描述
            tags: 标签列表
            kb_id: 指定ID（可选）

        Returns:
            创建的知识库对象
        """
        kb_id = kb_id or self.generate_kb_id()
        now = datetime.now().isoformat()

        kb = KnowledgeBase(
            id=kb_id,
            name=name,
            files=files or [],
            file_infos=file_infos or [],
            created_at=now,
            updated_at=now,
            description=description,
            tags=tags or [],
        )

        # 创建知识库目录
        kb_path = self.get_kb_path(kb_id)
        kb_path.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (kb_path / "chroma").mkdir(exist_ok=True)

        # 更新索引
        self._index[kb_id] = kb
        self._save_index()

        return kb

    def get_kb(self, kb_id: str) -> Optional[KnowledgeBase]:
        """获取知识库信息"""
        return self._index.get(kb_id)

    def list_kbs(self, enabled_only: bool = False) -> List[KnowledgeBase]:
        """
        列出所有知识库

        Args:
            enabled_only: 是否只列出启用的知识库

        Returns:
            知识库列表
        """
        kbs = list(self._index.values())
        if enabled_only:
            kbs = [kb for kb in kbs if kb.enabled]
        return sorted(kbs, key=lambda x: x.updated_at, reverse=True)

    def search_kbs(self, keyword: str) -> List[KnowledgeBase]:
        """
        搜索知识库

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的知识库列表
        """
        keyword = keyword.lower()
        results = []
        for kb in self._index.values():
            if (keyword in kb.name.lower() or
                keyword in kb.description.lower() or
                any(keyword in tag.lower() for tag in kb.tags) or
                any(keyword in f.lower() for f in kb.files)):
                results.append(kb)
        return sorted(results, key=lambda x: x.updated_at, reverse=True)

    def update_kb(self, kb_id: str, **kwargs) -> Optional[KnowledgeBase]:
        """
        更新知识库信息

        Args:
            kb_id: 知识库ID
            **kwargs: 要更新的字段

        Returns:
            更新后的知识库对象
        """
        kb = self._index.get(kb_id)
        if not kb:
            return None

        for key, value in kwargs.items():
            if hasattr(kb, key):
                setattr(kb, key, value)

        kb.updated_at = datetime.now().isoformat()
        self._save_index()
        return kb

    def delete_kb(self, kb_id: str) -> bool:
        """
        删除知识库

        Args:
            kb_id: 知识库ID

        Returns:
            是否删除成功
        """
        if kb_id not in self._index:
            return False

        # 删除目录
        kb_path = self.get_kb_path(kb_id)
        if kb_path.exists():
            try:
                shutil.rmtree(kb_path)
            except Exception as e:
                print(f"删除知识库目录失败: {e}")
                return False

        # 更新索引
        del self._index[kb_id]
        self._save_index()
        return True

    def kb_exists(self, kb_id: str) -> bool:
        """检查知识库是否存在"""
        return kb_id in self._index

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        total_kbs = len(self._index)
        enabled_kbs = sum(1 for kb in self._index.values() if kb.enabled)
        total_docs = sum(kb.doc_count for kb in self._index.values())
        total_chunks = sum(kb.chunk_count for kb in self._index.values())
        total_entities = sum(kb.entity_count for kb in self._index.values())
        total_relations = sum(kb.relation_count for kb in self._index.values())

        return {
            "total_kbs": total_kbs,
            "enabled_kbs": enabled_kbs,
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "total_entities": total_entities,
            "total_relations": total_relations,
        }

    # ========== 数据存储方法 ==========

    def save_meta(self, kb_id: str, meta: Dict) -> bool:
        """保存知识库元数据"""
        kb_path = self.get_kb_path(kb_id)
        meta_path = kb_path / "meta.json"
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存元数据失败: {e}")
            return False

    def load_meta(self, kb_id: str) -> Optional[Dict]:
        """加载知识库元数据"""
        kb_path = self.get_kb_path(kb_id)
        meta_path = kb_path / "meta.json"
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载元数据失败: {e}")
            return None

    def save_splits(self, kb_id: str, splits: List[Dict]) -> bool:
        """
        保存文本片段

        Args:
            kb_id: 知识库ID
            splits: 片段列表，每个元素包含 page_content 和 metadata

        Returns:
            是否保存成功
        """
        kb_path = self.get_kb_path(kb_id)
        splits_path = kb_path / "splits.json"
        try:
            with open(splits_path, "w", encoding="utf-8") as f:
                json.dump(splits, f, ensure_ascii=False, indent=2)
            # 更新片段数量
            self.update_kb(kb_id, chunk_count=len(splits))
            return True
        except Exception as e:
            print(f"保存文本片段失败: {e}")
            return False

    def load_splits(self, kb_id: str) -> Optional[List[Dict]]:
        """加载文本片段"""
        kb_path = self.get_kb_path(kb_id)
        splits_path = kb_path / "splits.json"
        if not splits_path.exists():
            return None
        try:
            with open(splits_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载文本片段失败: {e}")
            return None

    def save_graph(self, kb_id: str, graph_data: Dict) -> bool:
        """
        保存知识图谱

        Args:
            kb_id: 知识库ID
            graph_data: 知识图谱数据，包含 entities 和 relations

        Returns:
            是否保存成功
        """
        kb_path = self.get_kb_path(kb_id)
        graph_path = kb_path / "graph.json"
        try:
            with open(graph_path, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            # 更新实体和关系数量
            entity_count = len(graph_data.get("entities", {}))
            relation_count = len(graph_data.get("relations", []))
            self.update_kb(kb_id, entity_count=entity_count, relation_count=relation_count)
            return True
        except Exception as e:
            print(f"保存知识图谱失败: {e}")
            return False

    def load_graph(self, kb_id: str) -> Optional[Dict]:
        """加载知识图谱"""
        kb_path = self.get_kb_path(kb_id)
        graph_path = kb_path / "graph.json"
        if not graph_path.exists():
            return None
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载知识图谱失败: {e}")
            return None

    def get_chroma_path(self, kb_id: str) -> Path:
        """获取ChromaDB存储路径"""
        return self.get_kb_path(kb_id) / "chroma"

    def has_chroma_data(self, kb_id: str) -> bool:
        """检查是否有ChromaDB数据"""
        chroma_path = self.get_chroma_path(kb_id)
        # 检查是否有数据文件
        return any(chroma_path.glob("*.sqlite3")) or any(chroma_path.glob("**/data_level0.bin"))

    def has_graph_data(self, kb_id: str) -> bool:
        """检查是否有知识图谱数据"""
        kb_path = self.get_kb_path(kb_id)
        graph_path = kb_path / "graph.json"
        return graph_path.exists()


class MultiKnowledgeBaseRetriever:
    """多知识库检索器 - 支持合并多个知识库进行检索"""

    def __init__(self, kb_manager: KnowledgeBaseManager):
        self.kb_manager = kb_manager
        self._loaded_vectorstores = {}
        self._loaded_graphs = {}

    def load_knowledge_bases(self, kb_ids: List[str], embeddings) -> Tuple[List, List]:
        """
        加载多个知识库的数据

        Args:
            kb_ids: 知识库ID列表
            embeddings: embedding函数

        Returns:
            (vectorstores列表, graphs列表)
        """
        import chromadb
        from .knowledge_base_manager import KnowledgeBaseSerializer

        vectorstores = []
        graphs = []

        for kb_id in kb_ids:
            kb = self.kb_manager.get_kb(kb_id)
            if not kb:
                continue

            # 加载向量存储
            if self.kb_manager.has_chroma_data(kb_id):
                try:
                    chroma_path = str(self.kb_manager.get_chroma_path(kb_id))
                    client = chromadb.PersistentClient(path=chroma_path)
                    collection = client.get_or_create_collection("all-my-documents")
                    # 这里需要CustomChromaVectorStore，在页面中处理
                    vectorstores.append((kb_id, chroma_path, collection))
                except Exception as e:
                    print(f"加载向量存储失败 {kb_id}: {e}")

            # 加载知识图谱
            graph_data = self.kb_manager.load_graph(kb_id)
            if graph_data:
                graph = KnowledgeBaseSerializer.dict_to_graph(graph_data)
                graphs.append(graph)

        return vectorstores, graphs

    def merge_search_results(self, results_list: List[List], top_k: int = 6) -> List:
        """
        合并多个检索结果

        Args:
            results_list: 多个检索结果列表
            top_k: 返回的结果数量

        Returns:
            合并后的结果列表
        """
        all_results = []
        seen_content = set()

        for results in results_list:
            for doc in results:
                # 简单去重
                content_hash = hash(doc.page_content[:100])
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    all_results.append(doc)

        return all_results[:top_k]


class KnowledgeBaseSerializer:
    """知识图谱序列化器 - 用于保存和加载KnowledgeGraph对象"""

    @staticmethod
    def graph_to_dict(graph) -> Dict:
        """
        将KnowledgeGraph对象转换为字典

        Args:
            graph: KnowledgeGraph实例

        Returns:
            包含entities和relations的字典
        """
        from graphrag import Entity, Relation

        entities = {}
        for name, entity in graph.entities.items():
            entities[name] = {
                "name": entity.name,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "mentions": entity.mentions,
                "aliases": getattr(entity, 'aliases', []),
                "source_context": getattr(entity, 'source_context', ""),
            }

        relations = []
        seen_relations = set()
        for relation in graph.relations:
            rel_key = (relation.source, relation.target, relation.relation_type)
            if rel_key not in seen_relations:
                seen_relations.add(rel_key)
                relations.append({
                    "source": relation.source,
                    "target": relation.target,
                    "relation_type": relation.relation_type,
                    "context": relation.context,
                    "weight": relation.weight,
                    "confidence": getattr(relation, 'confidence', 1.0),
                    "source_sentence": getattr(relation, 'source_sentence', ""),
                })

        return {"entities": entities, "relations": relations}

    @staticmethod
    def dict_to_graph(data: Dict):
        """
        从字典重建KnowledgeGraph对象

        Args:
            data: 包含entities和relations的字典

        Returns:
            KnowledgeGraph实例
        """
        from graphrag import Entity, Relation, KnowledgeGraph

        graph = KnowledgeGraph()

        # 重建实体
        for name, entity_data in data.get("entities", {}).items():
            entity = Entity(
                name=entity_data["name"],
                entity_type=entity_data["entity_type"],
                description=entity_data.get("description", ""),
                mentions=entity_data.get("mentions", 1),
                aliases=entity_data.get("aliases", []),
                source_context=entity_data.get("source_context", ""),
            )
            graph.add_entity(entity)

        # 重建关系
        for rel_data in data.get("relations", []):
            relation = Relation(
                source=rel_data["source"],
                target=rel_data["target"],
                relation_type=rel_data["relation_type"],
                context=rel_data.get("context", ""),
                weight=rel_data.get("weight", 1.0),
                confidence=rel_data.get("confidence", 1.0),
                source_sentence=rel_data.get("source_sentence", ""),
            )
            graph.add_relation(relation)

        return graph

    @staticmethod
    def splits_to_dict(splits) -> List[Dict]:
        """
        将文档片段列表转换为可序列化的字典列表

        Args:
            splits: Document对象列表

        Returns:
            字典列表
        """
        return [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in splits
        ]

    @staticmethod
    def dict_to_splits(splits_data: List[Dict]):
        """
        从字典列表重建Document对象列表

        Args:
            splits_data: 字典列表

        Returns:
            Document对象列表
        """
        from langchain_core.documents import Document

        return [
            Document(page_content=item["page_content"], metadata=item.get("metadata", {}))
            for item in splits_data
        ]

    @staticmethod
    def merge_graphs(graphs: List):
        """
        合并多个知识图谱

        Args:
            graphs: KnowledgeGraph对象列表

        Returns:
            合并后的KnowledgeGraph
        """
        from graphrag import KnowledgeGraph

        merged = KnowledgeGraph()

        for graph in graphs:
            # 合并实体
            for name, entity in graph.entities.items():
                if name in merged.entities:
                    merged.entities[name].mentions += entity.mentions
                    if entity.description and not merged.entities[name].description:
                        merged.entities[name].description = entity.description
                else:
                    merged.entities[name] = entity

            # 合并关系
            for relation in graph.relations:
                # 检查是否已存在相同关系
                exists = False
                for r in merged.relations:
                    if (r.source == relation.source and
                        r.target == relation.target and
                        r.relation_type == relation.relation_type):
                        exists = True
                        break
                if not exists:
                    merged.add_relation(relation)

        return merged
