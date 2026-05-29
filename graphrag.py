"""
GraphRAG 知识图谱增强模块
实现基于知识图谱的文档检索增强
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


@dataclass
class Relation:
    """关系类"""

    source: str
    target: str
    relation_type: str
    context: str = ""
    weight: float = 1.0


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
                    entities.append(
                        Entity(
                            name=entity_name,
                            entity_type=entity_type,
                            description=context[:100],  # 正确使用 description 参数
                        )
                    )

        # 额外：提取引号中的内容作为实体
        quoted_pattern = r'[""「」『』【】](.+?)[""「」『』【】]'
        quoted_matches = re.findall(quoted_pattern, text)
        for match in quoted_matches:
            if len(match) >= 2 and len(match) <= 20:
                entities.append(
                    Entity(
                        name=match, entity_type="概念", description=f"引号中提到的概念"
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
                                    relations.append(
                                        Relation(
                                            source=source,
                                            target=target,
                                            relation_type=relation_type,
                                            context=text[:100],
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
                    relations.append(
                        Relation(
                            source=source,
                            target=target,
                            relation_type="并列",
                            context=text[:100],
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
{text}

请返回如下格式的JSON：
{{"entities": [{{"name": "实体名", "type": "类型", "description": "简短描述"}}]}}

只返回JSON，不要其他内容。"""

            response = self.llm.invoke(prompt)
            content = (
                response.content if hasattr(response, "content") else str(response)
            )

            # 提取JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return [
                    Entity(
                        name=e["name"],
                        entity_type=e.get("type", "未知"),
                        description=e.get("description", ""),
                    )
                    for e in data.get("entities", [])
                ]
        except Exception as e:
            print(f"LLM实体提取错误: {e}")

        return []

    def build_from_documents(
        self, documents: List[str], use_llm: bool = False
    ) -> KnowledgeGraph:
        """
        从文档构建知识图谱（LLM+规则混合，消歧、过滤）
        """
        self.graph = KnowledgeGraph()
        entity_dict = {}  # name -> Entity
        relation_set = set()  # (source, target, relation_type)

        for doc in documents:
            entities = []
            relations = []
            # LLM增强提取
            if use_llm and self.llm:
                try:
                    llm_entities = self.extract_entities_llm(doc)
                    entities.extend(llm_entities)
                except Exception as e:
                    print(f"LLM实体抽取异常: {e}")
            # 规则补充
            try:
                rule_entities = self.extract_entities_rules(doc)
                entities.extend(rule_entities)
            except Exception as e:
                print(f"规则实体抽取异常: {e}")
            # 实体消歧与去重
            for ent in entities:
                key = ent.name.strip()
                if not key or len(key) < 2 or len(key) > 20:
                    continue
                # 类型优先LLM结果
                if key in entity_dict:
                    if ent.entity_type != "未知":
                        entity_dict[key].entity_type = ent.entity_type
                    entity_dict[key].mentions += 1
                else:
                    entity_dict[key] = ent

            # 关系抽取（LLM可扩展，暂用规则）
            try:
                rule_relations = self.extract_relations_rules(doc)
                relations.extend(rule_relations)
            except Exception as e:
                print(f"规则关系抽取异常: {e}")
            # 关系过滤
            for rel in relations:
                s, t = rel.source.strip(), rel.target.strip()
                if (
                    not s
                    or not t
                    or s == t
                    or len(s) < 2
                    or len(t) < 2
                    or len(s) > 20
                    or len(t) > 20
                ):
                    continue
                rel_key = (s, t, rel.relation_type)
                if rel_key not in relation_set:
                    relation_set.add(rel_key)
        # 添加实体
        for ent in entity_dict.values():
            self.graph.add_entity(ent)
        # 添加关系
        for s, t, rtype in relation_set:
            self.graph.add_relation(Relation(source=s, target=t, relation_type=rtype))
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

    # 实体类型颜色映射
    ENTITY_COLORS = {
        "人物": "#FF6B6B",  # 红色
        "组织": "#4ECDC4",  # 青色
        "地点": "#45B7D1",  # 蓝色
        "时间": "#96CEB4",  # 绿色
        "产品": "#FFEAA7",  # 黄色
        "事件": "#DDA0DD",  # 紫色
        "概念": "#98D8C8",  # 薄荷绿
        "数值": "#F7DC6F",  # 金色
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

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def generate_html_visualization(
        self, height: int = 600, physics: bool = True, show_edge_labels: bool = False
    ) -> str:
        """
        生成交互式HTML可视化

        Args:
            height: 画布高度
            physics: 是否启用物理引擎
            show_edge_labels: 是否显示边的label（关系类型）

        Returns:
            HTML字符串
        """
        if not self.graph.entities:
            return "<p>知识图谱为空，无法可视化</p>"

        # 构建节点数据
        nodes = []
        for entity in self.graph.entities.values():
            color = self.ENTITY_COLORS.get(entity.entity_type, "#CCCCCC")
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

        # 构建边数据
        edges = []
        seen_edges = set()  # 避免重复边
        for relation in self.graph.relations:
            edge_key = (relation.source, relation.target, relation.relation_type)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                color, style = self.RELATION_STYLES.get(
                    relation.relation_type, ("#999999", "solid")
                )
                edge = {
                    "from": relation.source,
                    "to": relation.target,
                    "color": color,
                    "dashes": style == "dashed",
                    "smooth": True,
                }
                if show_edge_labels:
                    edge["label"] = relation.relation_type
                edges.append(edge)

        # 生成HTML
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
    </style>
</head>
<body>
    <div id="mynetwork"></div>
    <div class="legend">
        <strong>实体类型图例：</strong><br>
        {self._generate_legend()}
    </div>

    <script>
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
    </script>
</body>
</html>
"""
        return html

    def _generate_legend(self) -> str:
        """生成图例HTML"""
        legend_items = []
        for entity_type, color in self.ENTITY_COLORS.items():
            legend_items.append(
                f'<span class="legend-item"><span class="legend-color" style="background:{color}"></span>{entity_type}</span>'
            )
        return "".join(legend_items)

    def _to_json(self, data: list) -> str:
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
