"""
知识库管理页面
支持查看、创建、编辑、删除知识库
支持查看和编辑知识图谱
"""

import streamlit as st
import os
import pandas as pd
from datetime import datetime
from login import require_login
from knowledge_base_manager import (
    KnowledgeBaseManager,
    KnowledgeBaseSerializer,
)

# ========== 页面配置 ==========
st.set_page_config(
    page_title="知识库管理 - 智能助手",
    page_icon="📚",
    layout="wide",
)

# ========== 统一登录检查 ==========
require_login()

# ========== 初始化 ==========
if "kb_manager" not in st.session_state:
    st.session_state.kb_manager = KnowledgeBaseManager()

kb_manager = st.session_state.kb_manager

# ========== 页面标题 ==========
st.title("📚 知识库管理")
st.markdown("---")

# ========== 统计信息 ==========
stats = kb_manager.get_stats()
stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
with stat_col1:
    st.metric("知识库总数", stats["total_kbs"])
with stat_col2:
    st.metric("文档总数", stats["total_docs"])
with stat_col3:
    st.metric("片段总数", stats["total_chunks"])
with stat_col4:
    st.metric("实体总数", stats["total_entities"])
with stat_col5:
    st.metric("关系总数", stats["total_relations"])

st.markdown("---")

# ========== 主界面布局 ==========
tab1, tab2, tab3 = st.tabs(["📋 知识库列表", "➕ 创建知识库", "🔧 知识图谱管理"])

# ==================== Tab1: 知识库列表 ====================
with tab1:
    st.subheader("所有知识库")

    # 搜索和筛选
    search_col1, search_col2, search_col3 = st.columns([2, 1, 1])
    with search_col1:
        search_keyword = st.text_input("🔍 搜索知识库", placeholder="输入名称、描述或文件名...")
    with search_col2:
        filter_status = st.selectbox("状态筛选", ["全部", "已启用", "已禁用"])
    with search_col3:
        sort_by = st.selectbox("排序方式", ["更新时间", "创建时间", "名称", "文档数"])

    # 获取知识库列表
    if search_keyword:
        kbs = kb_manager.search_kbs(search_keyword)
    else:
        kbs = kb_manager.list_kbs()

    # 筛选状态
    if filter_status == "已启用":
        kbs = [kb for kb in kbs if kb.enabled]
    elif filter_status == "已禁用":
        kbs = [kb for kb in kbs if not kb.enabled]

    # 排序
    if sort_by == "创建时间":
        kbs = sorted(kbs, key=lambda x: x.created_at, reverse=True)
    elif sort_by == "名称":
        kbs = sorted(kbs, key=lambda x: x.name)
    elif sort_by == "文档数":
        kbs = sorted(kbs, key=lambda x: x.doc_count, reverse=True)

    # 显示知识库列表
    if not kbs:
        st.info("📭 暂无知识库，请切换到「创建知识库」标签页创建新知识库")
    else:
        for kb in kbs:
            # 知识库卡片
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                status_icon = "✅" if kb.enabled else "❌"
                st.markdown(f"### {status_icon} {kb.name}")
                if kb.description:
                    st.caption(f"📝 {kb.description}")
                if kb.tags:
                    tags_html = " ".join([f'<span style="background:#e0e0e0;padding:2px 8px;border-radius:10px;font-size:0.8em;margin-right:5px;">{tag}</span>' for tag in kb.tags])
                    st.markdown(tags_html, unsafe_allow_html=True)

            with col2:
                st.metric("文档/片段", f"{kb.doc_count} / {kb.chunk_count}")
                st.metric("实体/关系", f"{kb.entity_count} / {kb.relation_count}")

            with col3:
                st.caption(f"🕐 创建: {kb.created_at[:19] if kb.created_at else 'N/A'}")
                st.caption(f"🔄 更新: {kb.updated_at[:19] if kb.updated_at else 'N/A'}")

            with col4:
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("👁️", key=f"detail_{kb.id}", help="查看详情"):
                        st.session_state.selected_kb_id = kb.id
                with btn_col2:
                    new_status = not kb.enabled
                    btn_text = "🔴" if kb.enabled else "🟢"
                    if st.button(btn_text, key=f"toggle_{kb.id}", help="启用/禁用"):
                        kb_manager.update_kb(kb.id, enabled=new_status)
                        st.rerun()
                with btn_col3:
                    if st.button("🗑️", key=f"delete_{kb.id}", help="删除"):
                        if kb_manager.delete_kb(kb.id):
                            st.success(f"已删除: {kb.name}")
                            st.rerun()

            # 来源文件
            with st.expander(f"📎 来源文件 ({len(kb.files)}个)"):
                if kb.files:
                    file_df_data = []
                    file_infos_list = kb.file_infos if kb.file_infos else []
                    for i, fname in enumerate(kb.files):
                        file_info = {}
                        for fi in file_infos_list:
                            if isinstance(fi, dict) and fi.get("name") == fname:
                                file_info = fi
                                break
                        size_str = "N/A"
                        if file_info.get("size"):
                            try:
                                size_val = int(file_info.get("size", 0))
                                if size_val > 1024 * 1024:
                                    size_str = f"{size_val / (1024 * 1024):.1f} MB"
                                else:
                                    size_str = f"{size_val / 1024:.1f} KB"
                            except:
                                size_str = "N/A"
                        file_df_data.append({
                            "序号": i + 1,
                            "文件名": fname,
                            "大小": size_str,
                        })
                    st.dataframe(pd.DataFrame(file_df_data), hide_index=True, use_container_width=True)
                else:
                    st.info("无文件信息")

            st.divider()

# ========== 知识库详情面板（使用expander替代dialog）==========
if "selected_kb_id" in st.session_state and st.session_state.selected_kb_id:
    kb = kb_manager.get_kb(st.session_state.selected_kb_id)
    if kb:
        st.markdown("---")
        with st.container():
            st.markdown(f"## 📋 知识库详情：{kb.name}")

            col_close = st.columns([6, 1])
            with col_close[1]:
                if st.button("❌ 关闭", key="close_detail"):
                    st.session_state.selected_kb_id = None
                    st.rerun()

            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown("### 📋 基本信息")
                st.write(f"**ID**: `{kb.id}`")
                st.write(f"**状态**: {'✅ 已启用' if kb.enabled else '❌ 已禁用'}")
                st.write(f"**创建时间**: {kb.created_at[:19] if kb.created_at else 'N/A'}")
                st.write(f"**更新时间**: {kb.updated_at[:19] if kb.updated_at else 'N/A'}")

                st.markdown("### 📝 描述")
                st.write(kb.description or "暂无描述")

                st.markdown("### 🏷️ 标签")
                if kb.tags:
                    st.write(", ".join(kb.tags))
                else:
                    st.write("暂无标签")

            with detail_col2:
                st.markdown("### 📊 统计信息")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("文档数量", kb.doc_count)
                    st.metric("实体数量", kb.entity_count)
                with c2:
                    st.metric("片段数量", kb.chunk_count)
                    st.metric("关系数量", kb.relation_count)

                st.markdown("### 📎 来源文件")
                if kb.files:
                    for fname in kb.files[:10]:
                        st.write(f"- {fname}")
                    if len(kb.files) > 10:
                        st.write(f"... 共 {len(kb.files)} 个文件")
                else:
                    st.write("暂无文件信息")

            st.markdown("---")
            st.markdown("### ✏️ 编辑知识库")

            edit_col1, edit_col2, edit_col3 = st.columns(3)
            with edit_col1:
                new_name = st.text_input("名称", value=kb.name, key=f"edit_name_{kb.id}")
            with edit_col2:
                new_desc = st.text_input("描述", value=kb.description, key=f"edit_desc_{kb.id}")
            with edit_col3:
                new_tags = st.text_input("标签(逗号分隔)", value=",".join(kb.tags), key=f"edit_tags_{kb.id}")

            if st.button("💾 保存修改", key=f"save_edit_{kb.id}"):
                tags_list = [t.strip() for t in new_tags.split(",") if t.strip()]
                kb_manager.update_kb(kb.id, name=new_name, description=new_desc, tags=tags_list)
                st.success("已保存修改")
                st.rerun()

# ==================== Tab2: 创建知识库 ====================
with tab2:
    st.subheader("创建新知识库")

    create_col1, create_col2 = st.columns([2, 1])

    with create_col1:
        st.markdown("### 📝 基本信息")
        new_kb_name = st.text_input("知识库名称 *", placeholder="例如：合同范本知识库")
        new_kb_desc = st.text_area("描述", placeholder="描述这个知识库的用途、内容等...")
        new_kb_tags = st.text_input("标签(逗号分隔)", placeholder="例如：合同,法律,范本")

    with create_col2:
        st.markdown("### 📎 上传文件")
        uploaded_files = st.file_uploader(
            "选择文件",
            type=["txt", "docx", "doc", "pdf"],
            accept_multiple_files=True,
            key="create_kb_uploader",
        )

        if uploaded_files:
            st.info(f"已选择 {len(uploaded_files)} 个文件")
            for f in uploaded_files:
                st.write(f"- {f.name} ({f.size / 1024:.1f} KB)")

    st.markdown("---")
    if st.button("🚀 创建知识库", type="primary", use_container_width=True):
        if not new_kb_name:
            st.error("请输入知识库名称")
        elif not uploaded_files:
            st.error("请上传至少一个文件")
        else:
            file_infos = [{"name": f.name, "size": f.size, "path": ""} for f in uploaded_files]
            tags_list = [t.strip() for t in new_kb_tags.split(",") if t.strip()]

            new_kb = kb_manager.create_kb(
                name=new_kb_name,
                files=[f.name for f in uploaded_files],
                file_infos=file_infos,
                description=new_kb_desc,
                tags=tags_list,
            )

            st.session_state.new_kb_files = uploaded_files
            st.session_state.new_kb_id = new_kb.id
            st.success(f"✅ 知识库「{new_kb_name}」创建成功！ID: {new_kb.id}")
            st.info("请前往「文档检索」页面上传文件并构建向量库和知识图谱")

# ==================== Tab3: 知识图谱管理 ====================
with tab3:
    st.subheader("知识图谱管理")

    kbs_with_graph = [kb for kb in kb_manager.list_kbs() if kb_manager.has_graph_data(kb.id)]

    if not kbs_with_graph:
        st.info("📭 暂无知识图谱数据，请先在文档检索页面构建知识图谱")
    else:
        graph_col1, graph_col2 = st.columns([1, 2])

        with graph_col1:
            st.markdown("### 选择知识库")

            selected_kb_ids = []
            for kb in kbs_with_graph:
                if st.checkbox(f"{kb.name} ({kb.entity_count}实体)", key=f"graph_kb_{kb.id}"):
                    selected_kb_ids.append(kb.id)

        with graph_col2:
            if selected_kb_ids:
                st.markdown("### 知识图谱预览")

                for kb_id in selected_kb_ids:
                    kb = kb_manager.get_kb(kb_id)
                    if kb:
                        st.markdown(f"#### {kb.name}")

                        graph_data = kb_manager.load_graph(kb_id)
                        if graph_data:
                            graph = KnowledgeBaseSerializer.dict_to_graph(graph_data)

                            # 实体列表
                            with st.expander(f"📌 实体列表 ({len(graph.entities)}个)", expanded=False):
                                entity_data = []
                                for name, entity in graph.entities.items():
                                    entity_data.append({
                                        "名称": name,
                                        "类型": entity.entity_type,
                                        "出现次数": entity.mentions,
                                        "描述": (entity.description[:50] + "...") if len(entity.description) > 50 else entity.description,
                                    })
                                st.dataframe(pd.DataFrame(entity_data), hide_index=True, use_container_width=True)

                            # 关系列表
                            with st.expander(f"🔗 关系列表 ({len(graph.relations)}个)", expanded=False):
                                relation_data = []
                                for r in graph.relations:
                                    relation_data.append({
                                        "源实体": r.source,
                                        "关系": r.relation_type,
                                        "目标实体": r.target,
                                    })
                                st.dataframe(pd.DataFrame(relation_data), hide_index=True, use_container_width=True)

                            # 编辑实体
                            with st.expander("✏️ 编辑实体", expanded=False):
                                entity_names = list(graph.entities.keys())
                                if entity_names:
                                    selected_entity = st.selectbox("选择实体", options=entity_names, key=f"edit_entity_select_{kb_id}")

                                    if selected_entity:
                                        entity = graph.entities[selected_entity]
                                        new_type = st.selectbox(
                                            "实体类型",
                                            options=["人物", "组织", "地点", "时间", "产品", "事件", "概念", "数值", "其他"],
                                            index=["人物", "组织", "地点", "时间", "产品", "事件", "概念", "数值", "其他"].index(entity.entity_type) if entity.entity_type in ["人物", "组织", "地点", "时间", "产品", "事件", "概念", "数值"] else 8,
                                            key=f"entity_type_{kb_id}_{selected_entity}",
                                        )
                                        new_desc = st.text_area("描述", value=entity.description, key=f"entity_desc_{kb_id}_{selected_entity}")

                                        c_a, c_b = st.columns(2)
                                        with c_a:
                                            if st.button("💾 保存", key=f"save_entity_{kb_id}_{selected_entity}"):
                                                entity.entity_type = new_type
                                                entity.description = new_desc
                                                graph_data = KnowledgeBaseSerializer.graph_to_dict(graph)
                                                kb_manager.save_graph(kb_id, graph_data)
                                                st.success("已保存")
                                                st.rerun()
                                        with c_b:
                                            if st.button("🗑️ 删除", key=f"del_entity_{kb_id}_{selected_entity}"):
                                                if selected_entity in graph.entities:
                                                    del graph.entities[selected_entity]
                                                    graph.relations = [r for r in graph.relations if r.source != selected_entity and r.target != selected_entity]
                                                    graph_data = KnowledgeBaseSerializer.graph_to_dict(graph)
                                                    kb_manager.save_graph(kb_id, graph_data)
                                                    st.success("已删除")
                                                    st.rerun()

                            # 添加实体
                            with st.expander("➕ 添加实体", expanded=False):
                                a1, a2, a3 = st.columns(3)
                                with a1:
                                    add_name = st.text_input("名称", key=f"add_name_{kb_id}")
                                with a2:
                                    add_type = st.selectbox("类型", options=["人物", "组织", "地点", "时间", "产品", "事件", "概念", "数值"], key=f"add_type_{kb_id}")
                                with a3:
                                    add_desc = st.text_input("描述", key=f"add_desc_{kb_id}")

                                if st.button("添加", key=f"add_entity_btn_{kb_id}"):
                                    if add_name and add_name not in graph.entities:
                                        from graphrag import Entity
                                        new_entity = Entity(name=add_name, entity_type=add_type, description=add_desc, mentions=1)
                                        graph.add_entity(new_entity)
                                        graph_data = KnowledgeBaseSerializer.graph_to_dict(graph)
                                        kb_manager.save_graph(kb_id, graph_data)
                                        st.success(f"已添加: {add_name}")
                                        st.rerun()
                                    elif add_name in graph.entities:
                                        st.warning("实体已存在")

                            # 添加关系
                            with st.expander("➕ 添加关系", expanded=False):
                                r1, r2, r3 = st.columns(3)
                                with r1:
                                    rel_source = st.selectbox("源实体", options=entity_names, key=f"rel_source_{kb_id}")
                                with r2:
                                    rel_type = st.selectbox("关系", options=["属于", "包含", "负责", "位于", "开发", "使用", "提供", "合作", "关联"], key=f"rel_type_{kb_id}")
                                with r3:
                                    rel_target = st.selectbox("目标实体", options=entity_names, key=f"rel_target_{kb_id}")

                                if st.button("添加关系", key=f"add_rel_btn_{kb_id}"):
                                    if rel_source and rel_target and rel_source != rel_target:
                                        from graphrag import Relation
                                        new_rel = Relation(source=rel_source, target=rel_target, relation_type=rel_type)
                                        graph.add_relation(new_rel)
                                        graph_data = KnowledgeBaseSerializer.graph_to_dict(graph)
                                        kb_manager.save_graph(kb_id, graph_data)
                                        st.success(f"已添加: {rel_source} --[{rel_type}]--> {rel_target}")
                                        st.rerun()

                        st.divider()
            else:
                st.info("👈 请选择要查看的知识库")

# ========== 页脚 ==========
st.markdown("---")
st.caption("💡 提示：知识库数据永久存储在本地，下次登录仍可使用")
