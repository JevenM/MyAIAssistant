"""
GraphRAG 知识图谱增强模块
实现基于知识图谱的文档检索增强
支持LLM+规则混合抽取、实体消歧、关系过滤、可视化交互
"""

import re
import json
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field


@dataclass
class Entity:
    """实体类"""

    name: str
    entity_type: str
    description: str = ""
    mentions: int = 1
    aliases: List[str] = field(default_factory=list)  # 别名列表
    source_context: str = ""  # 来源上下文


@dataclass
class Relation:
    """关系类"""

    source: str
    target: str
    relation_type: str
    context: str = ""
    weight: float = 1.0
    confidence: float = 1.0  # 置信度
    source_sentence: str = ""  # 来源句子


@dataclass
class KnowledgeGraph:
    """知识图谱类"""

    entities: Dict[str, Entity] = field(default_factory=dict)
    relations: List[Relation] = field(default_factory=list)
    entity_relations: Dict[str, List[str]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add_entity(self, entity: Entity):
        """添加实体"""
        if entity.name in self.entities:
            self.entities[entity.name].mentions += 1
        else:
            self.entities[entity.name] = entity

    def add_relation(self, relation: Relation):
        """添加关系"""
        self.relations.append(relation)
        self.entity_relations[relation.source].append(relation.target)
        self.entity_relations[relation.target].append(relation.source)

    def get_related_entities(self, entity_name: str, depth: int = 2) -> Set[str]:
        """获取相关实体（BFS遍历）"""
        visited = set()
        current_level = {entity_name}

        for _ in range(depth):
            next_level = set()
            for entity in current_level:
                if entity not in visited:
                    visited.add(entity)
                    next_level.update(self.entity_relations.get(entity, []))
            current_level = next_level - visited

        return visited

    def get_entity_context(self, entity_name: str) -> str:
        """获取实体上下文信息"""
        if entity_name not in self.entities:
            return ""

        entity = self.entities[entity_name]
        related = self.get_related_entities(entity_name, depth=1)

        context = f"实体：{entity_name}（{entity.entity_type}）\n"
        if entity.description:
            context += f"描述：{entity.description}\n"

        if related:
            context += f"相关实体：{', '.join(list(related)[:10])}\n"

        return context

    def get_entity_relations_detail(self, entity_name: str) -> Dict:
        """
        获取实体的详细关系信息（用于可视化弹窗）

        Returns:
            包含出边关系、入边关系、相关实体、相关文档片段的字典
        """
        if entity_name not in self.entities:
            return {}

        entity = self.entities[entity_name]

        # 出边关系
        out_relations = [
            {
                "target": r.target,
                "type": r.relation_type,
                "context": r.context,
                "sentence": r.source_sentence,
            }
            for r in self.relations
            if r.source == entity_name
        ]

        # 入边关系
        in_relations = [
            {
                "source": r.source,
                "type": r.relation_type,
                "context": r.context,
                "sentence": r.source_sentence,
            }
            for r in self.relations
            if r.target == entity_name
        ]

        # 相关实体
        related = self.get_related_entities(entity_name, depth=2)
        related_with_type = [
            {"name": name, "type": self.entities[name].entity_type}
            for name in related
            if name in self.entities and name != entity_name
        ]

        # 相关文档片段（从关系上下文中提取）
        contexts = set()
        for r in self.relations:
            if r.source == entity_name or r.target == entity_name:
                if r.context:
                    contexts.add(r.context[:200])
        doc_fragments = list(contexts)[:5]

        return {
            "entity": {
                "name": entity.name,
                "type": entity.entity_type,
                "mentions": entity.mentions,
                "description": entity.description,
            },
            "out_relations": out_relations[:10],
            "in_relations": in_relations[:10],
            "related_entities": related_with_type[:15],
            "doc_fragments": doc_fragments,
        }


class EntityDisambiguator:
    """实体消歧与标准化器"""

    # 常见同义词词典（可扩展）
    SYNONYM_DICT = {
        # 人物称谓
        "张三老师": "张三",
        "张先生": "张三",
        "李四博士": "李四",
        "李博士": "李四",
        # 组织简称
        "阿里": "阿里巴巴",
        "阿里巴巴集团": "阿里巴巴",
        "腾讯公司": "腾讯",
        "百度公司": "百度",
        # 地点简称
        "北京城": "北京",
        "上海城": "上海",
    }

    # 实体类型标准化映射
    TYPE_NORMALIZATION = {
        "人": "人物",
        "员": "人物",
        "师": "人物",
        "公司": "组织",
        "企业": "组织",
        "集团": "组织",
        "省": "地点",
        "市": "地点",
        "县": "地点",
        "年": "时间",
        "月": "时间",
        "日": "时间",
    }

    def __init__(self, custom_synonyms: Dict[str, str] = None):
        """
        初始化消歧器

        Args:
            custom_synonyms: 自定义同义词词典
        """
        self.synonyms = {**self.SYNONYM_DICT, **(custom_synonyms or {})}

    def normalize_entity_name(self, name: str) -> str:
        """标准化实体名称"""
        # 去除前后空格
        name = name.strip()

        # 查找同义词
        if name in self.synonyms:
            return self.synonyms[name]

        # 去除常见后缀（如"的"、"了"等）
        name = re.sub(r"[的了吗呢]", "", name)

        return name

    def normalize_entity_type(self, entity_type: str) -> str:
        """标准化实体类型"""
        if entity_type in self.TYPE_NORMALIZATION:
            return self.TYPE_NORMALIZATION[entity_type]
        return entity_type

    def is_same_entity(self, name1: str, name2: str) -> bool:
        """判断两个名称是否指向同一实体"""
        n1 = self.normalize_entity_name(name1)
        n2 = self.normalize_entity_name(name2)
        return n1 == n2

    def merge_entities(self, entities: List[Entity]) -> List[Entity]:
        """
        合并重复实体

        Args:
            entities: 原始实体列表

        Returns:
            合并后的实体列表
        """
        merged = {}
        for entity in entities:
            normalized_name = self.normalize_entity_name(entity.name)
            normalized_type = self.normalize_entity_type(entity.entity_type)

            if normalized_name in merged:
                # 合并信息
                merged[normalized_name].mentions += entity.mentions
                if entity.description and not merged[normalized_name].description:
                    merged[normalized_name].description = entity.description
                if entity.name != normalized_name:
                    if entity.name not in merged[normalized_name].aliases:
                        merged[normalized_name].aliases.append(entity.name)
            else:
                entity.name = normalized_name
                entity.entity_type = normalized_type
                merged[normalized_name] = entity

        return list(merged.values())


class RelationFilter:
    """关系过滤器"""

    # 无效关系词（通常是误判）
    INVALID_RELATION_WORDS = {
        "的",
        "是",
        "了",
        "和",
        "与",
        "在",
        "有",
        "为",
        "这",
        "那",
        "他",
        "她",
        "它",
        "我",
        "你",
        "可以",
        "可能",
        "应该",
        "必须",
        "需要",
    }

    # 有效关系类型
    VALID_RELATION_TYPES = {
        "属于",
        "包含",
        "负责",
        "位于",
        "成立于",
        "开发",
        "创造",
        "发明",
        "使用",
        "采用",
        "利用",
        "提供",
        "支持",
        "合作",
        "隶属于",
        "导致",
        "引起",
        "称为",
        "叫做",
        "名为",
        "并列",
        "关联",
        "相关",
    }

    def __init__(self, min_entity_len: int = 2, max_entity_len: int = 20):
        """
        初始化关系过滤器

        Args:
            min_entity_len: 实体最小长度
            max_entity_len: 实体最大长度
        """
        self.min_entity_len = min_entity_len
        self.max_entity_len = max_entity_len

    def is_valid_entity(self, name: str) -> bool:
        """检查实体是否有效"""
        if not name:
            return False

        # 长度检查
        if len(name) < self.min_entity_len or len(name) > self.max_entity_len:
            return False

        # 纯数字检查
        if name.isdigit():
            return False

        # 纯标点检查
        if re.match(r"^[^\w一-鿿]+$", name):
            return False

        # 无效词检查
        if name in self.INVALID_RELATION_WORDS:
            return False

        return True

    def is_valid_relation_type(self, relation_type: str) -> bool:
        """检查关系类型是否有效"""
        if not relation_type:
            return False
        return relation_type in self.VALID_RELATION_TYPES or len(relation_type) >= 2

    def filter_relation(self, relation: Relation) -> Tuple[bool, str]:
        """
        过滤单个关系

        Returns:
            (是否有效, 原因)
        """
        # 实体有效性检查
        if not self.is_valid_entity(relation.source):
            return False, f"源实体无效: {relation.source}"
        if not self.is_valid_entity(relation.target):
            return False, f"目标实体无效: {relation.target}"

        # 自引用检查
        if relation.source == relation.target:
            return False, "自引用关系"

        # 关系类型检查
        if not self.is_valid_relation_type(relation.relation_type):
            return False, f"关系类型无效: {relation.relation_type}"

        # 实体相似度检查（避免相似实体间的无意义关系）
        if self._is_similar_entity(relation.source, relation.target):
            return False, f"实体过于相似: {relation.source} vs {relation.target}"

        return True, "有效"

    def _is_similar_entity(self, name1: str, name2: str) -> bool:
        """检查两个实体是否过于相似"""
        # 完全包含
        if name1 in name2 or name2 in name1:
            return True

        # 计算字符重叠率
        common = set(name1) & set(name2)
        if len(common) / max(len(set(name1)), len(set(name2))) > 0.8:
            return True

        return False

    def filter_relations(self, relations: List[Relation]) -> List[Relation]:
        """过滤关系列表"""
        filtered = []
        for rel in relations:
            is_valid, reason = self.filter_relation(rel)
            if is_valid:
                filtered.append(rel)
            else:
                print(f"关系过滤: {reason}")
        return filtered


class GraphRAGBuilder:
    """知识图谱构建器"""

    # 常见实体类型（扩展版）
    ENTITY_TYPES = {
        "人物": [
            "人",
            "先生",
            "女士",
            "教授",
            "博士",
            "经理",
            "主任",
            "工程师",
            "作者",
            "编辑",
            "员",
            "师",
            "长",
            "家",
            "者",
            "手",
            "工",
            "生",
        ],
        "组织": [
            "公司",
            "集团",
            "企业",
            "机构",
            "大学",
            "学院",
            "研究所",
            "部门",
            "团队",
            "中心",
            "局",
            "院",
            "校",
            "所",
            "会",
            "社",
            "厂",
        ],
        "地点": [
            "省",
            "市",
            "县",
            "区",
            "镇",
            "村",
            "路",
            "街",
            "大楼",
            "中心",
            "广场",
            "公园",
            "机场",
            "车站",
            "港口",
            "岛",
            "山",
            "河",
        ],
        "时间": ["年", "月", "日", "时", "分", "秒", "世纪", "年代", "周", "季度"],
        "产品": [
            "系统",
            "平台",
            "软件",
            "硬件",
            "设备",
            "产品",
            "服务",
            "应用",
            "APP",
            "工具",
        ],
        "事件": [
            "会议",
            "活动",
            "项目",
            "计划",
            "任务",
            "研究",
            "比赛",
            "展览",
            "发布会",
        ],
        "概念": [
            "技术",
            "方法",
            "理论",
            "模型",
            "算法",
            "框架",
            "协议",
            "标准",
            "规范",
        ],
        "数值": ["亿元", "万元", "元", "美元", "亿", "万", "千", "百", "%", "百分比"],
    }

    # 常见关系类型（扩展版）
    RELATION_PATTERNS = [
        # 基础关系
        (r"(.+?)是(.+?)的(.+)", "属于"),
        (r"(.+?)包括(.+?)和(.+)", "包含"),
        (r"(.+?)包含(.+)", "包含"),
        (r"(.+?)负责(.+)", "负责"),
        (r"(.+?)位于(.+)", "位于"),
        (r"(.+?)成立于(.+)", "成立于"),
        # 开发/创造关系
        (r"(.+?)开发了(.+)", "开发"),
        (r"(.+?)创造了(.+)", "创造"),
        (r"(.+?)发明了(.+)", "发明"),
        # 使用关系
        (r"(.+?)使用(.+)", "使用"),
        (r"(.+?)采用(.+)", "采用"),
        (r"(.+?)利用(.+)", "利用"),
        # 提供关系
        (r"(.+?)提供(.+)", "提供"),
        (r"(.+?)支持(.+)", "支持"),
        # 合作关系
        (r"(.+?)与(.+?)合作", "合作"),
        (r"(.+?)和(.+?)合作", "合作"),
        # 隶属关系
        (r"(.+?)属于(.+)", "属于"),
        (r"(.+?)隶属于(.+)", "隶属于"),
        # 因果关系
        (r"(.+?)导致(.+)", "导致"),
        (r"(.+?)引起(.+)", "引起"),
        # 其他关系
        (r"(.+?)称为(.+)", "称为"),
        (r"(.+?)叫做(.+)", "叫做"),
        (r"(.+?)名为(.+)", "名为"),
    ]

    def __init__(self, llm=None):
        """
        初始化知识图谱构建器

        Args:
            llm: 大语言模型实例（可选，用于更精确的抽取）
        """
        self.llm = llm
        self.graph = KnowledgeGraph()
        self.disambiguator = EntityDisambiguator()
        self.relation_filter = RelationFilter()

    def _extract_sentence_context(
        self, text: str, entity_name: str, window: int = 50
    ) -> str:
        """提取实体所在的句子上下文"""
        sentences = re.split(r"[。！？\n]", text)
        for sentence in sentences:
            if entity_name in sentence:
                return sentence.strip()
        return text[:100]

    def extract_entities_rules(self, text: str) -> List[Entity]:
        """基于规则的实体提取"""
        entities = []

        # 基于实体类型关键词提取
        for entity_type, keywords in self.ENTITY_TYPES.items():
            for keyword in keywords:
                # 改进的正则：匹配更长的实体名（1-20个字符）
                pattern = rf"([一-鿿A-Za-z0-9]{{1,20}}){keyword}"
                matches = re.findall(pattern, text)
                for match in matches:
                    entity_name = match + keyword
                    # 获取实体上下文（前后各50字符）
                    start_idx = max(0, text.find(entity_name) - 50)
                    end_idx = min(
                        len(text), text.find(entity_name) + len(entity_name) + 50
                    )
                    context = text[start_idx:end_idx]
                    sentence = self._extract_sentence_context(text, entity_name)
                    entities.append(
                        Entity(
                            name=entity_name,
                            entity_type=entity_type,
                            description=context[:100],
                            source_context=sentence,
                        )
                    )

        # 额外：提取引号中的内容作为实体
        quoted_pattern = r'[""「」『』【】](.+?)[""「」『』【】]'
        quoted_matches = re.findall(quoted_pattern, text)
        for match in quoted_matches:
            if len(match) >= 2 and len(match) <= 20:
                sentence = self._extract_sentence_context(text, match)
                entities.append(
                    Entity(
                        name=match,
                        entity_type="概念",
                        description="引号中提到的概念",
                        source_context=sentence,
                    )
                )

        return entities

    def extract_relations_rules(self, text: str) -> List[Relation]:
        """基于规则的关系抽取"""
        relations = []

        for pattern, relation_type in self.RELATION_PATTERNS:
            try:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        if len(match) >= 2:
                            source = match[0].strip()
                            target = match[-1].strip()
                            # 过滤太短或太长的实体
                            if (
                                source
                                and target
                                and 2 <= len(source) <= 20
                                and 2 <= len(target) <= 20
                            ):
                                # 避免自引用
                                if source != target:
                                    sentence = self._extract_sentence_context(
                                        text, source
                                    )
                                    relations.append(
                                        Relation(
                                            source=source,
                                            target=target,
                                            relation_type=relation_type,
                                            context=text[:100],
                                            source_sentence=sentence,
                                        )
                                    )
            except Exception as e:
                print(f"关系抽取正则错误: {pattern}, {e}")
                continue

        # 额外：提取"X和Y"并列关系
        并列_pattern = r"([一-鿿A-Za-z0-9]{2,10})和([一-鿿A-Za-z0-9]{2,10})"
        并列_matches = re.findall(并列_pattern, text)
        for match in 并列_matches:
            if len(match) == 2:
                source, target = match[0].strip(), match[1].strip()
                if source != target:
                    sentence = self._extract_sentence_context(text, source)
                    relations.append(
                        Relation(
                            source=source,
                            target=target,
                            relation_type="并列",
                            context=text[:100],
                            source_sentence=sentence,
                        )
                    )

        return relations

    def extract_entities_llm(self, text: str) -> List[Entity]:
        """使用大模型提取实体"""
        if not self.llm:
            return []

        try:
            prompt = f"""请从以下文本中提取实体，按JSON格式返回：

文本：
{text[:2000]}

请返回如下格式的JSON：
{{"entities": [{{"name": "实体名", "type": "类型（人物/组织/地点/时间/产品/事件/概念/数值）", "description": "简短描述"}}]}}

要求：
1. 只提取文本中明确提到的实体
2. 类型必须从给定类型中选择
3. 描述要简洁，不超过50字
4. 只返回JSON，不要其他内容。"""

            response = self.llm.invoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            # 提取JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                entities = []
                for e in data.get("entities", []):
                    sentence = self._extract_sentence_context(text, e["name"])
                    entities.append(
                        Entity(
                            name=e["name"],
                            entity_type=e.get("type", "未知"),
                            description=e.get("description", ""),
                            source_context=sentence,
                        )
                    )
                return entities
        except Exception as e:
            print(f"LLM实体提取错误: {e}")

        return []

    def extract_relations_llm(
        self, text: str, entities: List[Entity] = None
    ) -> List[Relation]:
        """
        使用大模型提取关系

        Args:
            text: 文本内容
            entities: 已知实体列表（可选，用于指导抽取）

        Returns:
            关系列表
        """
        if not self.llm:
            return []

        try:
            # 构建实体提示
            entity_hint = ""
            if entities:
                entity_names = [e.name for e in entities[:20]]
                entity_hint = f"\n\n已知实体：{', '.join(entity_names)}"

            prompt = f"""请从以下文本中提取实体之间的关系，按JSON格式返回：

文本：
{text[:2000]}
{entity_hint}

请返回如下格式的JSON：
{{"relations": [{{"source": "源实体", "target": "目标实体", "type": "关系类型", "description": "关系描述"}}]}}

关系类型包括：属于、包含、负责、位于、成立于、开发、创造、发明、使用、采用、提供、支持、合作、导致、称为、关联等。

要求：
1. 只提取文本中明确表达的关系
2. source和target必须是文本中提到的实体
3. 关系类型要准确
4. 只返回JSON，不要其他内容。"""

            response = self.llm.invoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            # 提取JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                relations = []
                for r in data.get("relations", []):
                    sentence = self._extract_sentence_context(text, r.get("source", ""))
                    relations.append(
                        Relation(
                            source=r["source"],
                            target=r["target"],
                            relation_type=r.get("type", "关联"),
                            context=text[:100],
                            confidence=0.8,  # LLM抽取的关系置信度
                            source_sentence=sentence,
                        )
                    )
                return relations
        except Exception as e:
            print(f"LLM关系提取错误: {e}")

        return []

    def build_from_documents(
        self,
        documents: List[str],
        use_llm: bool = False,
        show_progress: callable = None,
    ) -> KnowledgeGraph:
        """
        从文档构建知识图谱（LLM+规则混合，消歧、过滤）

        Args:
            documents: 文档列表
            use_llm: 是否使用LLM增强抽取
            show_progress: 进度回调函数

        Returns:
            构建的知识图谱
        """
        self.graph = KnowledgeGraph()
        entity_dict = {}  # name -> Entity
        relation_set = set()  # (source, target, relation_type)
        all_relations = []  # 存储所有关系用于过滤

        total_docs = len(documents)
        for idx, doc in enumerate(documents):
            if show_progress:
                show_progress(idx + 1, total_docs, f"处理文档 {idx + 1}/{total_docs}")

            entities = []
            relations = []

            # LLM增强提取
            if use_llm and self.llm:
                try:
                    llm_entities = self.extract_entities_llm(doc)
                    entities.extend(llm_entities)

                    # LLM关系抽取
                    llm_relations = self.extract_relations_llm(doc, llm_entities)
                    relations.extend(llm_relations)
                except Exception as e:
                    print(f"LLM抽取异常: {e}")

            # 规则补充
            try:
                rule_entities = self.extract_entities_rules(doc)
                entities.extend(rule_entities)
            except Exception as e:
                print(f"规则实体抽取异常: {e}")

            try:
                rule_relations = self.extract_relations_rules(doc)
                relations.extend(rule_relations)
            except Exception as e:
                print(f"规则关系抽取异常: {e}")

            # 实体消歧与去重
            merged_entities = self.disambiguator.merge_entities(entities)

            for ent in merged_entities:
                key = ent.name.strip()
                if not key or len(key) < 2 or len(key) > 20:
                    continue

                if key in entity_dict:
                    entity_dict[key].mentions += ent.mentions
                    if ent.description and not entity_dict[key].description:
                        entity_dict[key].description = ent.description
                    if ent.source_context and not entity_dict[key].source_context:
                        entity_dict[key].source_context = ent.source_context
                else:
                    entity_dict[key] = ent

            # 收集所有关系
            all_relations.extend(relations)

        # 关系过滤
        if show_progress:
            show_progress(total_docs, total_docs, "过滤关系...")

        filtered_relations = self.relation_filter.filter_relations(all_relations)

        # 添加实体
        for ent in entity_dict.values():
            self.graph.add_entity(ent)

        # 添加过滤后的关系
        for rel in filtered_relations:
            s, t = rel.source.strip(), rel.target.strip()
            rel_key = (s, t, rel.relation_type)
            if rel_key not in relation_set:
                relation_set.add(rel_key)
                # 确保实体存在
                if s not in self.graph.entities:
                    self.graph.add_entity(Entity(name=s, entity_type="未知"))
                if t not in self.graph.entities:
                    self.graph.add_entity(Entity(name=t, entity_type="未知"))
                self.graph.add_relation(rel)

        return self.graph

    def get_graph_summary(self) -> str:
        """获取知识图谱摘要"""
        if not self.graph.entities:
            return "知识图谱为空"

        summary = f"📊 知识图谱统计：\n"
        summary += f"- 实体数量：{len(self.graph.entities)}\n"
        summary += f"- 关系数量：{len(self.graph.relations)}\n\n"

        # 实体类型分布
        type_counts = defaultdict(int)
        for entity in self.graph.entities.values():
            type_counts[entity.entity_type] += 1

        summary += "实体类型分布：\n"
        for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            summary += f"  - {etype}: {count}\n"

        # 高频实体
        top_entities = sorted(
            self.graph.entities.values(), key=lambda x: x.mentions, reverse=True
        )[:10]

        summary += "\n高频实体：\n"
        for entity in top_entities:
            summary += (
                f"  - {entity.name}（{entity.entity_type}）：{entity.mentions}次\n"
            )

        return summary


class GraphRAGRetriever:
    """GraphRAG检索器"""

    def __init__(self, graph: KnowledgeGraph, vectorstore, top_k: int = 4):
        """
        初始化检索器

        Args:
            graph: 知识图谱
            vectorstore: 向量存储
            top_k: 返回结果数量
        """
        self.graph = graph
        self.vectorstore = vectorstore
        self.top_k = top_k

    def retrieve(self, query: str) -> Tuple[List, str]:
        """
        混合检索：向量检索 + 知识图谱增强

        Args:
            query: 查询文本

        Returns:
            Tuple[List, str]: (检索结果, 知识图谱上下文)
        """
        # 1. 向量检索
        vector_results = self.vectorstore.similarity_search(query, k=self.top_k)

        # 2. 从查询中提取可能的实体
        related_entities = set()
        for entity_name in self.graph.entities:
            if entity_name in query:
                related_entities.update(self.graph.get_related_entities(entity_name))

        # 3. 构建知识图谱上下文
        kg_context = ""
        if related_entities:
            kg_context = "\n\n📚 知识图谱相关背景：\n"
            for entity_name in list(related_entities)[:5]:
                context = self.graph.get_entity_context(entity_name)
                if context:
                    kg_context += f"\n{context}"

        return vector_results, kg_context

    def retrieve_with_expansion(
        self, query: str, expansion_depth: int = 1
    ) -> Tuple[List, str]:
        """
        带查询扩展的检索

        Args:
            query: 查询文本
            expansion_depth: 实体扩展深度

        Returns:
            Tuple[List, str]: (检索结果, 知识图谱上下文)
        """
        # 基础检索
        results, kg_context = self.retrieve(query)

        # 实体扩展检索
        for entity_name in self.graph.entities:
            if entity_name in query:
                related = self.graph.get_related_entities(
                    entity_name, depth=expansion_depth
                )
                for related_entity in list(related)[:3]:
                    expanded_results = self.vectorstore.similarity_search(
                        related_entity, k=2
                    )
                    for doc in expanded_results:
                        if doc not in results:
                            results.append(doc)

        return results[: self.top_k * 2], kg_context


class KnowledgeGraphVisualizer:
    """知识图谱可视化器"""

    # 实体类型颜色映射 - 单一定义源
    ENTITY_COLORS = {
        "人物": "#E74C3C",  # 鲜红
        "组织": "#3498DB",  # 亮蓝
        "地点": "#2ECC71",  # 翠绿
        "时间": "#F39C12",  # 橙色
        "产品": "#9B59B6",  # 紫罗兰
        "事件": "#1ABC9C",  # 青绿
        "概念": "#E91E63",  # 粉红
        "数值": "#00BCD4",  # 青色
    }

    # 关系类型样式映射
    RELATION_STYLES = {
        "属于": ("#666666", "dashed"),
        "包含": ("#4CAF50", "solid"),
        "负责": ("#FF9800", "solid"),
        "位于": ("#2196F3", "solid"),
        "开发": ("#9C27B0", "solid"),
        "使用": ("#00BCD4", "dashed"),
        "提供": ("#8BC34A", "solid"),
        "合作": ("#FF5722", "dashed"),
        "并列": ("#607D8B", "dotted"),
    }

    @classmethod
    def get_entity_color(cls, entity_type: str) -> str:
        """获取实体类型对应的颜色"""
        return cls.ENTITY_COLORS.get(entity_type, "#95A5A6")  # 默认灰色

    @classmethod
    def get_colors_js_object(cls) -> str:
        """生成JavaScript颜色对象代码"""
        items = [f"'{k}': '{v}'" for k, v in cls.ENTITY_COLORS.items()]
        return (
            "{\n                "
            + ",\n                ".join(items)
            + "\n            }"
        )

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def _get_entity_detail_fallback(self, entity_name: str) -> Dict:
        """
        获取实体详情的备用方法（兼容旧版本KnowledgeGraph）

        Args:
            entity_name: 实体名称

        Returns:
            实体详情字典
        """
        if entity_name not in self.graph.entities:
            return {}

        entity = self.graph.entities[entity_name]

        # 出边关系
        out_relations = [
            {
                "target": r.target,
                "type": r.relation_type,
                "context": getattr(r, "context", ""),
                "sentence": getattr(r, "source_sentence", ""),
            }
            for r in self.graph.relations
            if r.source == entity_name
        ]

        # 入边关系
        in_relations = [
            {
                "source": r.source,
                "type": r.relation_type,
                "context": getattr(r, "context", ""),
                "sentence": getattr(r, "source_sentence", ""),
            }
            for r in self.graph.relations
            if r.target == entity_name
        ]

        # 相关实体
        related = self.graph.get_related_entities(entity_name, depth=2)
        related_with_type = []
        for name in related:
            if name in self.graph.entities and name != entity_name:
                ent = self.graph.entities[name]
                related_with_type.append(
                    {"name": name, "type": getattr(ent, "entity_type", "未知")}
                )

        # 相关文档片段
        contexts = set()
        for r in self.graph.relations:
            if r.source == entity_name or r.target == entity_name:
                ctx = getattr(r, "context", "")
                if ctx:
                    contexts.add(ctx[:200])
        doc_fragments = list(contexts)[:5]

        return {
            "entity": {
                "name": entity.name,
                "type": getattr(entity, "entity_type", "未知"),
                "mentions": getattr(entity, "mentions", 1),
                "description": getattr(entity, "description", ""),
            },
            "out_relations": out_relations[:10],
            "in_relations": in_relations[:10],
            "related_entities": related_with_type[:15],
            "doc_fragments": doc_fragments,
        }

    def generate_html_visualization(
        self,
        height: int = 700,
        physics: bool = True,
        show_edge_labels: bool = False,
        filter_types: list = None,
        use_3d: bool = False,
    ) -> str:
        """
        生成交互式HTML可视化（支持节点双击弹窗和3D模式）

        Args:
            height: 画布高度
            physics: 是否启用物理引擎
            show_edge_labels: 是否显示边的label（关系类型）
            filter_types: 要显示的实体类型列表，None表示显示所有
            use_3d: 是否使用3D可视化

        Returns:
            HTML字符串
        """
        if not self.graph.entities:
            return "<p>知识图谱为空，无法可视化</p>"

        # 构建节点数据
        nodes = []
        entity_details = {}  # 用于弹窗的实体详情

        for entity in self.graph.entities.values():
            # 如果指定了筛选类型，且当前实体类型不在筛选列表中，则跳过
            if filter_types is not None and entity.entity_type not in filter_types:
                continue

            color = self.get_entity_color(entity.entity_type)
            nodes.append(
                {
                    "id": entity.name,
                    "label": entity.name,
                    "title": f"{entity.name}\n类型: {entity.entity_type}\n出现: {entity.mentions}次",
                    "color": color,
                    "size": min(20 + entity.mentions * 2, 40),
                    "group": entity.entity_type,
                }
            )
            # 获取实体详情用于弹窗（兼容旧版本KnowledgeGraph）
            if hasattr(self.graph, "get_entity_relations_detail"):
                entity_details[entity.name] = self.graph.get_entity_relations_detail(
                    entity.name
                )
            else:
                entity_details[entity.name] = self._get_entity_detail_fallback(
                    entity.name
                )

        # 构建边数据（只包含已筛选节点的边）
        edges = []
        seen_edges = set()  # 避免重复边
        node_ids = {n["id"] for n in nodes}  # 已筛选的节点ID集合

        for relation in self.graph.relations:
            # 只添加两端节点都在筛选结果中的边
            if relation.source not in node_ids or relation.target not in node_ids:
                continue

            edge_key = (relation.source, relation.target, relation.relation_type)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                color, style = self.RELATION_STYLES.get(
                    relation.relation_type, ("#999999", "solid")
                )
                edge = {
                    "from": relation.source,
                    "to": relation.target,
                    "source": relation.source,
                    "target": relation.target,
                    "color": color,
                    "dashes": style == "dashed",
                    "smooth": True,
                    "relation_type": relation.relation_type,
                }
                if show_edge_labels:
                    edge["label"] = relation.relation_type
                edges.append(edge)

        if use_3d:
            return self._generate_3d_html(nodes, edges, entity_details, height)
        else:
            return self._generate_2d_html(
                nodes, edges, entity_details, height, physics, show_edge_labels
            )

    def _generate_2d_html(
        self, nodes, edges, entity_details, height, physics, show_edge_labels
    ) -> str:
        """生成2D可视化HTML"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>知识图谱可视化</title>
    <script src="https://unpkg.com/vis-network@9.1.0/dist/vis-network.min.js"></script>
    <style>
        #mynetwork {{
            width: 100%;
            height: {height}px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: #fafafa;
        }}
        .legend {{
            padding: 10px;
            background: white;
            border-radius: 8px;
            margin-top: 10px;
        }}
        .legend-item {{
            display: inline-block;
            margin: 5px 10px;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 3px;
            display: inline-block;
            margin-right: 5px;
        }}
        /* 弹窗样式 */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }}
        .modal-content {{
            background-color: #fefefe;
            margin: 5% auto;
            padding: 20px;
            border: 1px solid #888;
            border-radius: 10px;
            width: 80%;
            max-width: 600px;
            max-height: 80%;
            overflow-y: auto;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .modal-header {{
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .modal-title {{
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }}
        .modal-type {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            margin-left: 10px;
        }}
        .close {{
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }}
        .close:hover {{
            color: black;
        }}
        .entity-section {{
            margin-bottom: 15px;
        }}
        .entity-section h4 {{
            color: #666;
            margin-bottom: 8px;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }}
        .relation-item {{
            padding: 5px 0;
            border-bottom: 1px dashed #eee;
        }}
        .relation-arrow {{
            color: #4CAF50;
            margin: 0 5px;
        }}
        .tag {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.85em;
            margin-right: 5px;
            background: #e0e0e0;
        }}
    </style>
</head>
<body>
    <div id="mynetwork"></div>
    <div class="legend">
        <strong>实体类型图例：</strong><br>
        {self._generate_legend()}
        <br><small>💡 提示：双击节点可查看实体详情</small>
    </div>

    <!-- 弹窗 -->
    <div id="entityModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <div class="modal-header">
                <span class="modal-title" id="modalTitle">实体名称</span>
                <span class="modal-type" id="modalType">类型</span>
            </div>
            <div id="modalBody"></div>
        </div>
    </div>

    <script>
        // 实体详情数据
        const entityDetails = {self._to_json(entity_details)};

        // 节点数据
        var nodes = new vis.DataSet({self._to_json(nodes)});

        // 边数据
        var edges = new vis.DataSet({self._to_json(edges)});

        // 创建网络
        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        var options = {{
            nodes: {{
                shape: 'dot',
                font: {{
                    size: 14,
                    face: 'Arial'
                }},
                borderWidth: 2,
                shadow: true
            }},
            edges: {{
                width: 2,
                font: {{
                    size: 10,
                    align: 'middle'
                }},
                arrows: {{
                    to: {{ enabled: true, scaleFactor: 0.5 }}
                }},
                smooth: {{
                    type: 'continuous'
                }}
            }},
            physics: {{
                enabled: {str(physics).lower()},
                stabilization: {{
                    iterations: 200
                }},
                barnesHut: {{
                    gravitationalConstant: -2000,
                    springLength: 100
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 200,
                zoomView: true,
                dragView: true
            }}
        }};
        var network = new vis.Network(container, data, options);

        // 双击事件 - 显示实体详情弹窗
        network.on("doubleClick", function(params) {{
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                showEntityModal(nodeId);
            }}
        }});

        // 显示实体详情弹窗
        function showEntityModal(entityName) {{
            const detail = entityDetails[entityName];
            if (!detail) {{
                alert('未找到实体详情: ' + entityName);
                return;
            }}

            // 设置标题
            document.getElementById('modalTitle').textContent = detail.entity.name;

            // 设置类型标签（带颜色）
            const typeSpan = document.getElementById('modalType');
            typeSpan.textContent = detail.entity.type;
            const colors = {self.get_colors_js_object()};
            typeSpan.style.backgroundColor = colors[detail.entity.type] || '#95A5A6';

            // 构建内容
            let html = '';

            // 基本信息
            html += '<div class="entity-section">';
            html += '<p><strong>出现次数:</strong> ' + detail.entity.mentions + '</p>';
            if (detail.entity.description) {{
                html += '<p><strong>描述:</strong> ' + detail.entity.description + '</p>';
            }}
            html += '</div>';

            // 出边关系
            if (detail.out_relations && detail.out_relations.length > 0) {{
                html += '<div class="entity-section"><h4>🔗 出边关系</h4>';
                detail.out_relations.forEach(r => {{
                    html += '<div class="relation-item">';
                    html += '<span class="tag">' + r.type + '</span>';
                    html += '<span class="relation-arrow">→</span>';
                    html += '<strong>' + r.target + '</strong>';
                    html += '</div>';
                }});
                html += '</div>';
            }}

            // 入边关系
            if (detail.in_relations && detail.in_relations.length > 0) {{
                html += '<div class="entity-section"><h4>🔗 入边关系</h4>';
                detail.in_relations.forEach(r => {{
                    html += '<div class="relation-item">';
                    html += '<strong>' + r.source + '</strong>';
                    html += '<span class="relation-arrow">→</span>';
                    html += '<span class="tag">' + r.type + '</span>';
                    html += '</div>';
                }});
                html += '</div>';
            }}

            // 相关实体
            if (detail.related_entities && detail.related_entities.length > 0) {{
                html += '<div class="entity-section"><h4>🌐 相关实体</h4><p>';
                detail.related_entities.slice(0, 10).forEach(e => {{
                    html += '<span class="tag" style="background:' + (colors[e.type] || '#eee') + '">' + e.name + '</span> ';
                }});
                html += '</p></div>';
            }}

            // 相关文档片段
            if (detail.doc_fragments && detail.doc_fragments.length > 0) {{
                html += '<div class="entity-section"><h4>📄 相关文档片段</h4>';
                detail.doc_fragments.forEach((frag, i) => {{
                    html += '<div style="background:#f5f5f5;padding:8px;margin:5px 0;border-radius:4px;font-size:0.9em;">';
                    html += frag + '...';
                    html += '</div>';
                }});
                html += '</div>';
            }}

            document.getElementById('modalBody').innerHTML = html;
            document.getElementById('entityModal').style.display = 'block';
        }}

        // 关闭弹窗
        function closeModal() {{
            document.getElementById('entityModal').style.display = 'none';
        }}

        // 点击弹窗外部关闭
        window.onclick = function(event) {{
            var modal = document.getElementById('entityModal');
            if (event.target == modal) {{
                modal.style.display = 'none';
            }}
        }}
    </script>
</body>
</html>
"""
        return html

    def _generate_3d_html(self, nodes, edges, entity_details, height) -> str:
        """生成3D可视化HTML（使用3d-force-graph）- 高清光滑球体+完整关系表示"""
        import json

        # 转换数据格式为3d-force-graph格式
        graph_data = {
            "nodes": [
                {
                    "id": n["id"],
                    "name": n["label"],
                    "val": max(n["size"] / 6, 4),
                    "color": n["color"],
                    "group": n["group"],
                }
                for n in nodes
            ],
            "links": [
                {
                    "source": e["source"],
                    "target": e["target"],
                    "relation": e.get("relation_type", "关联"),
                }
                for e in edges
            ],
        }

        # 实体详情数据JSON
        entity_details_json = json.dumps(entity_details, ensure_ascii=False)
        graph_data_json = json.dumps(graph_data, ensure_ascii=False)
        colors_json = self.get_colors_js_object()

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>知识图谱3D可视化</title>
    <script src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
    <script src="https://unpkg.com/3d-force-graph@1.73.0/dist/3d-force-graph.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; font-family: 'Segoe UI', Arial, sans-serif; }}
        #graph-container {{
            width: 100%;
            height: {height}px;
            background: radial-gradient(circle at center, #1a1a2e 0%, #0d0d1a 50%, #050510 100%);
            cursor: grab;
        }}
        #graph-container:active {{
            cursor: grabbing;
        }}
        .legend {{
            position: absolute;
            top: 10px;
            left: 10px;
            padding: 15px;
            background: rgba(255,255,255,0.95);
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            max-width: 200px;
            z-index: 10;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 12px;
        }}
        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            display: inline-block;
        }}
        .controls {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            padding: 10px 15px;
            background: rgba(255,255,255,0.95);
            border-radius: 8px;
            font-size: 12px;
            z-index: 10;
        }}
        .tooltip {{
            position: fixed;
            padding: 15px;
            background: rgba(15,15,25,0.95);
            color: white;
            border-radius: 8px;
            font-size: 13px;
            pointer-events: none;
            display: none;
            z-index: 1000;
            max-width: 320px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .node-label {{
            position: fixed;
            padding: 8px 12px;
            background: rgba(255,255,255,0.98);
            border-radius: 6px;
            font-size: 13px;
            pointer-events: none;
            display: none;
            z-index: 50;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border: 1px solid #e0e0e0;
        }}
    </style>
</head>
<body>
    <div id="graph-container"></div>
    <div class="legend">
        <strong>实体类型图例</strong><br>
        <small style="color:#666">共 {len(nodes)} 个实体，{len(edges)} 条关系</small><br><br>
        {self._generate_3d_legend()}
    </div>

    <div class="tooltip" id="tooltip">
        <div id="tooltip-content"></div>
    </div>
    <div class="node-label" id="node-label"></div>

    <script>
        // 全局变量
        const container = document.getElementById('graph-container');
        const tooltip = document.getElementById('tooltip');
        const tooltipContent = document.getElementById('tooltip-content');
        const nodeLabel = document.getElementById('node-label');

        // 数据
        const graphData = {graph_data_json};
        const entityDetails = {entity_details_json};
        const colors = {colors_json};

        // 鼠标位置跟踪
        let mouseX = 0, mouseY = 0;
        document.addEventListener('mousemove', (e) => {{
            mouseX = e.clientX;
            mouseY = e.clientY;
        }});

        // 创建高分辨率球体几何体
        const sphereGeometry = new THREE.SphereGeometry(1, 64, 64);

        // 创建3D力图配置
        const Graph = ForceGraph3D()(container)
            .graphData(graphData)
            .nodeLabel('name')
            .nodeColor(d => d.color)
            .nodeVal(d => d.val)
            .nodeOpacity(0.95)
            .nodeThreeObject(node => {{
                // 创建光滑球体材质
                const material = new THREE.MeshPhongMaterial({{
                    color: node.color,
                    shininess: 120,
                    specular: new THREE.Color(0x555555),
                    transparent: true,
                    opacity: 0.95
                }});
                const mesh = new THREE.Mesh(sphereGeometry, material);
                mesh.scale.set(node.val, node.val, node.val);

                // 添加柔和发光效果
                const glowGeometry = new THREE.SphereGeometry(1.3, 32, 32);
                const glowMaterial = new THREE.MeshBasicMaterial({{
                    color: node.color,
                    transparent: true,
                    opacity: 0.12
                }});
                const glow = new THREE.Mesh(glowGeometry, glowMaterial);
                glow.scale.set(node.val, node.val, node.val);
                mesh.add(glow);

                return mesh;
            }})
            // 关系连线配置 - 清晰显示
            .linkWidth(2.5)
            .linkOpacity(0.8)
            .linkColor(() => 'rgba(200,200,220,0.7)')
            // 方向箭头配置
            .linkDirectionalArrowLength(12)
            .linkDirectionalArrowRelPos(0.95)
            .linkDirectionalArrowColor(() => 'rgba(220,220,240,0.9)')
            // 流动粒子效果 - 显示关系方向
            .linkDirectionalParticles(4)
            .linkDirectionalParticleSpeed(0.01)
            .linkDirectionalParticleWidth(3)
            .linkDirectionalParticleColor(() => 'rgba(100,180,255,0.8)')
            // 背景和场景
            .backgroundColor('rgba(0,0,0,0)')
            .showNavInfo(false)
            .enableNodeDrag(true)
            .enableNavigationControls(true)
            .cameraPosition({{ z: 300 }});

        // 添加环境光照
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        Graph.scene().add(ambientLight);

        // 添加定向光
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(100, 100, 100);
        Graph.scene().add(directionalLight);

        // 添加点光源
        const pointLight = new THREE.PointLight(0x6666ff, 0.4);
        pointLight.position.set(-100, -100, 100);
        Graph.scene().add(pointLight);

        // 添加顶部光源（让球体顶部更亮）
        const topLight = new THREE.DirectionalLight(0xffffff, 0.4);
        topLight.position.set(0, 200, 0);
        Graph.scene().add(topLight);

        // 节点点击事件 - 显示详情
        Graph.onNodeClick((node, event) => {{
            if (event) event.stopPropagation();
            showEntityInfo(node);
        }});

        // 节点悬停效果
        Graph.onNodeHover((node) => {{
            if (node) {{
                container.style.cursor = 'pointer';
                nodeLabel.innerHTML = `<strong style="color:${{node.color}}">${{node.name}}</strong><br><small style="color:#666">${{node.group}}</small>`;
                nodeLabel.style.display = 'block';
                updateLabelPosition();
            }} else {{
                container.style.cursor = container.dataset.dragging === 'true' ? 'grabbing' : 'grab';
                nodeLabel.style.display = 'none';
            }}
        }});

        // 更新标签位置
        function updateLabelPosition() {{
            if (nodeLabel.style.display === 'block') {{
                nodeLabel.style.left = (mouseX + 15) + 'px';
                nodeLabel.style.top = (mouseY - 10) + 'px';
                requestAnimationFrame(updateLabelPosition);
            }}
        }}

        // 显示实体信息弹窗
        function showEntityInfo(node) {{
            const detail = entityDetails[node.id];
            if (!detail) return;

            let html = '';
            html += `<div style="border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:10px;margin-bottom:12px;">`;
            html += `<strong style="font-size:18px;color:${{node.color}}">📌 ${{detail.entity.name}}</strong>`;
            html += `<span style="float:right;background:${{node.color}};color:white;padding:3px 10px;border-radius:4px;font-size:11px;">${{detail.entity.type}}</span>`;
            html += `</div>`;

            html += `<div style="color:#aaa;margin-bottom:10px;">出现次数: <span style="color:#fff;font-weight:bold;">${{detail.entity.mentions}}</span></div>`;

            if (detail.entity.description) {{
                html += `<div style="margin-bottom:15px;line-height:1.6;color:#ddd;">${{detail.entity.description.substring(0, 150)}}${{detail.entity.description.length > 150 ? '...' : ''}}</div>`;
            }}

            // 出边关系
            if (detail.out_relations && detail.out_relations.length > 0) {{
                html += `<div style="margin-bottom:12px;"><strong style="color:#4CAF50;">🔗 出边关系 (${{detail.out_relations.length}}):</strong></div>`;
                html += `<div style="max-height:100px;overflow-y:auto;margin-bottom:10px;">`;
                detail.out_relations.slice(0, 6).forEach(r => {{
                    const targetColor = colors[r.target] || '#aaa';
                    html += `<div style="margin:4px 0;padding:6px 8px;background:rgba(255,255,255,0.08);border-radius:4px;">`;
                    html += `<span style="color:${{node.color}}">${{node.name}}</span> <span style="color:#4CAF50">→</span> <strong style="color:${{targetColor}}">${{r.target}}</strong>`;
                    html += `<br><small style="color:#888;">(${{r.type}})</small>`;
                    html += `</div>`;
                }});
                if (detail.out_relations.length > 6) {{
                    html += `<div style="color:#666;font-size:11px;text-align:center;">...还有 ${{detail.out_relations.length - 6}} 个</div>`;
                }}
                html += `</div>`;
            }}

            // 入边关系
            if (detail.in_relations && detail.in_relations.length > 0) {{
                html += `<div style="margin-bottom:12px;"><strong style="color:#2196F3;">🔙 入边关系 (${{detail.in_relations.length}}):</strong></div>`;
                html += `<div style="max-height:100px;overflow-y:auto;">`;
                detail.in_relations.slice(0, 6).forEach(r => {{
                    const sourceColor = colors[r.source] || '#aaa';
                    html += `<div style="margin:4px 0;padding:6px 8px;background:rgba(255,255,255,0.08);border-radius:4px;">`;
                    html += `<strong style="color:${{sourceColor}}">${{r.source}}</strong> <span style="color:#2196F3">→</span> <span style="color:${{node.color}}">${{node.name}}</span>`;
                    html += `<br><small style="color:#888;">(${{r.type}})</small>`;
                    html += `</div>`;
                }});
                if (detail.in_relations.length > 6) {{
                    html += `<div style="color:#666;font-size:11px;text-align:center;">...还有 ${{detail.in_relations.length - 6}} 个</div>`;
                }}
                html += `</div>`;
            }}

            tooltipContent.innerHTML = html;
            tooltip.style.display = 'block';
            tooltip.style.left = Math.min(mouseX + 20, window.innerWidth - 340) + 'px';
            tooltip.style.top = Math.min(mouseY, window.innerHeight - 250) + 'px';

            // 8秒后自动隐藏
            setTimeout(() => {{
                hideTooltip();
            }}, 8000);
        }}

        function hideTooltip() {{
            tooltip.style.display = 'none';
        }}

        // 点击空白处隐藏tooltip
        Graph.onBackgroundClick(() => {{
            hideTooltip();
        }});

        // 跟踪拖拽状态
        container.addEventListener('mousedown', () => {{
            container.dataset.dragging = 'true';
            container.style.cursor = 'grabbing';
        }});
        container.addEventListener('mouseup', () => {{
            container.dataset.dragging = 'false';
            container.style.cursor = 'grab';
        }});

        // 窗口大小调整
        window.addEventListener('resize', () => {{
            Graph.width(container.clientWidth);
            Graph.height(container.clientHeight);
        }});

        // 初始大小设置
        Graph.width(container.clientWidth);
        Graph.height(container.clientHeight);

        // 添加背景星空效果（可选）
        function createStars() {{
            const starGeometry = new THREE.BufferGeometry();
            const starCount = 1000;
            const positions = new Float32Array(starCount * 3);
            for (let i = 0; i < starCount * 3; i++) {{
                positions[i] = (Math.random() - 0.5) * 2000;
            }}
            starGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            const starMaterial = new THREE.PointsMaterial({{ color: 0x444466, size: 2 }});
            const stars = new THREE.Points(starGeometry, starMaterial);
            Graph.scene().add(stars);
        }}
        createStars();
    </script>
</body>
</html>"""
        return html

    def _generate_3d_legend(self) -> str:
        """生成3D图例HTML"""
        legend_items = []
        for entity_type, color in self.ENTITY_COLORS.items():
            legend_items.append(
                f'<div class="legend-item"><span class="legend-color" style="background:{color}"></span>{entity_type}</div>'
            )
        return "".join(legend_items)

    def _generate_legend(self) -> str:
        """生成图例HTML"""
        legend_items = []
        for entity_type, color in self.ENTITY_COLORS.items():
            legend_items.append(
                f'<span class="legend-item"><span class="legend-color" style="background:{color}"></span>{entity_type}</span>'
            )
        return "".join(legend_items)

    def _to_json(self, data) -> str:
        """将数据转换为JSON字符串"""
        import json

        return json.dumps(data, ensure_ascii=False)


class ReasoningExplainer:
    """可解释性推理展示器"""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def explain_retrieval(
        self, query: str, retrieved_docs: List, found_entities: List[str] = None
    ) -> str:
        """
        生成检索推理路径解释

        Args:
            query: 用户查询
            retrieved_docs: 检索到的文档
            found_entities: 识别到的实体

        Returns:
            Markdown格式的推理解释
        """
        explanation = "## 🔍 检索推理路径\n\n"

        # Step 1: 查询分析
        explanation += "### 1️⃣ 查询分析\n"
        explanation += f"- **原始查询**: {query}\n"

        # Step 2: 实体识别
        explanation += "\n### 2️⃣ 实体识别\n"
        if found_entities:
            explanation += f"- 识别到 **{len(found_entities)}** 个实体：\n"
            for entity_name in found_entities[:5]:
                entity = self.graph.entities.get(entity_name)
                if entity:
                    explanation += f"  - `{entity_name}` ({entity.entity_type})\n"
        else:
            explanation += "- 未识别到已知实体，使用纯向量检索\n"

        # Step 3: 实体扩展
        explanation += "\n### 3️⃣ 知识图谱扩展\n"
        if found_entities:
            all_related = set()
            for entity_name in found_entities[:3]:
                related = self.graph.get_related_entities(entity_name, depth=1)
                all_related.update(related)

            if all_related:
                explanation += f"- 扩展找到 **{len(all_related)}** 个相关实体：\n"
                for related_entity in list(all_related)[:10]:
                    explanation += f"  - `{related_entity}`\n"
            else:
                explanation += "- 未找到相关实体\n"
        else:
            explanation += "- 跳过（无已知实体）\n"

        # Step 4: 文档检索
        explanation += "\n### 4️⃣ 文档检索\n"
        explanation += f"- 检索到 **{len(retrieved_docs)}** 个相关文档片段\n"

        # Step 5: 推理结论
        explanation += "\n### 5️⃣ 推理结论\n"
        if retrieved_docs:
            explanation += "- ✅ 基于检索结果生成回答\n"
        else:
            explanation += "- ⚠️ 未找到相关文档，可能需要更多信息\n"

        return explanation

    def explain_entity_relations(self, entity_name: str) -> str:
        """
        展示实体的关系推理链

        Args:
            entity_name: 实体名称

        Returns:
            Markdown格式的关系解释
        """
        if entity_name not in self.graph.entities:
            return f"实体 `{entity_name}` 不存在于知识图谱中"

        entity = self.graph.entities[entity_name]
        explanation = f"## 📊 实体分析: `{entity_name}`\n\n"
        explanation += f"- **类型**: {entity.entity_type}\n"
        explanation += f"- **出现次数**: {entity.mentions}\n"

        if entity.description:
            explanation += f"- **描述**: {entity.description[:100]}...\n"

        # 出边关系
        out_relations = [r for r in self.graph.relations if r.source == entity_name]
        in_relations = [r for r in self.graph.relations if r.target == entity_name]

        explanation += "\n### 🔗 出边关系\n"
        if out_relations:
            for r in out_relations[:10]:
                explanation += f"- `{r.source}` --[{r.relation_type}]--> `{r.target}`\n"
        else:
            explanation += "- 无\n"

        explanation += "\n### 🔐 入边关系\n"
        if in_relations:
            for r in in_relations[:10]:
                explanation += f"- `{r.source}` --[{r.relation_type}]--> `{r.target}`\n"
        else:
            explanation += "- 无\n"

        # 相关实体
        related = self.graph.get_related_entities(entity_name, depth=2)
        explanation += f"\n### 🌐 相关实体 (深度=2)\n"
        explanation += f"- 共 **{len(related)}** 个相关实体\n"
        for related_entity in list(related)[:15]:
            rel_entity = self.graph.entities.get(related_entity)
            if rel_entity:
                explanation += f"  - `{related_entity}` ({rel_entity.entity_type})\n"

        return explanation
