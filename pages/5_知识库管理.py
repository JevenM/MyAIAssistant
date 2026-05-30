"""
知识库管理页面
支持查看、创建、编辑、删除知识库
支持知识图谱可视化、编辑
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from login import require_login

# 公共工具模块
from kb_utils import (
    KnowledgeBaseManager,
    KnowledgeBaseSerializer,
    create_knowledge_base_full,
    render_graph_visualization,
    display_graph_stats,
    display_entity_table,
    display_relation_table,
    edit_entity,
    delete_entity,
    add_entity,
    add_relation,
    ENTITY_TYPES,
    RELATION_TYPES,
)
from graphrag import KnowledgeGraphVisualizer

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


# ========== 统计信息 ==========
stats = kb_manager.get_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("知识库总数", stats["total_kbs"])
c2.metric("文档总数", stats["total_docs"])
c3.metric("片段总数", stats["total_chunks"])
c4.metric("实体总数", stats["total_entities"])
c5.metric("关系总数", stats["total_relations"])

# st.markdown("---")

# ========== 主界面布局 ==========
tab1, tab2, tab3 = st.tabs(["📋 知识库列表", "➕ 创建知识库", "🌐 知识图谱"])

# ==================== Tab1: 知识库列表 ====================
with tab1:
    # 搜索和筛选
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_keyword = st.text_input("🔍 搜索", placeholder="名称、描述或文件名...")
    with col2:
        filter_status = st.selectbox("状态", ["全部", "已启用", "已禁用"])
    with col3:
        sort_by = st.selectbox("排序", ["更新时间", "创建时间", "名称", "文档数"])

    # 获取知识库列表
    kbs = (
        kb_manager.search_kbs(search_keyword)
        if search_keyword
        else kb_manager.list_kbs()
    )

    # 筛选
    if filter_status == "已启用":
        kbs = [kb for kb in kbs if kb.enabled]
    elif filter_status == "已禁用":
        kbs = [kb for kb in kbs if not kb.enabled]

    # 排序
    sort_keys = {"创建时间": "created_at", "名称": "name", "文档数": "doc_count"}
    if sort_by in sort_keys:
        kbs = sorted(
            kbs,
            key=lambda x: getattr(x, sort_keys[sort_by], ""),
            reverse=(sort_by != "名称"),
        )

    if not kbs:
        st.info("📭 暂无知识库，请切换到「创建知识库」标签页")
    else:
        for kb in kbs:
            with st.container():
                # 知识库卡片
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

                with col1:
                    icon = "✅" if kb.enabled else "❌"
                    st.markdown(f"### {icon} {kb.name}")
                    if kb.description:
                        st.caption(f"📝 {kb.description}")
                    if kb.tags:
                        tags = " ".join([f"`{t}`" for t in kb.tags])
                        st.markdown(tags)

                with col2:
                    st.metric("文档/片段", f"{kb.doc_count} / {kb.chunk_count}")
                    st.metric("实体/关系", f"{kb.entity_count} / {kb.relation_count}")

                with col3:
                    st.caption(f"🕐 {kb.created_at[:10] if kb.created_at else 'N/A'}")

                with col4:
                    b1, b2, b3 = st.columns(3)
                    if b1.button("👁️", key=f"view_{kb.id}", help="详情"):
                        st.session_state.view_kb_id = kb.id
                    if b2.button("🔴" if kb.enabled else "🟢", key=f"toggle_{kb.id}"):
                        kb_manager.update_kb(kb.id, enabled=not kb.enabled)
                        st.rerun()
                    if b3.button("🗑️", key=f"del_{kb.id}"):
                        kb_manager.delete_kb(kb.id)
                        st.success(f"已删除: {kb.name}")
                        st.rerun()

                # 文件列表
                with st.expander(f"📎 文件 ({len(kb.files)})"):
                    if kb.files:
                        file_data = []
                        for i, fname in enumerate(kb.files):
                            size = "N/A"
                            for fi in kb.file_infos or []:
                                if isinstance(fi, dict) and fi.get("name") == fname:
                                    val = fi.get("size", 0)
                                    size = f"{val/1024:.1f} KB" if val else "N/A"
                                    break
                            file_data.append(
                                {"序号": i + 1, "文件名": fname, "大小": size}
                            )
                        st.dataframe(pd.DataFrame(file_data), hide_index=True)
                    else:
                        st.info("无文件信息")

                st.divider()

    # 详情面板
    if "view_kb_id" in st.session_state and st.session_state.view_kb_id:
        kb = kb_manager.get_kb(st.session_state.view_kb_id)
        if kb:
            # st.markdown("---")
            st.markdown(f"## 📋 {kb.name}")
            if st.button("❌ 关闭"):
                st.session_state.view_kb_id = None
                st.rerun()

            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**ID**: `{kb.id}`")
                st.write(f"**状态**: {'✅' if kb.enabled else '❌'}")
                st.write(f"**描述**: {kb.description or '无'}")
                st.write(f"**标签**: {', '.join(kb.tags) if kb.tags else '无'}")
            with c2:
                st.metric("文档", kb.doc_count)
                st.metric("片段", kb.chunk_count)
                st.metric("实体", kb.entity_count)
                st.metric("关系", kb.relation_count)

# ==================== Tab2: 创建知识库 ====================
with tab2:
    st.markdown("### 创建新知识库")

    c1, c2 = st.columns([2, 1])
    with c1:
        name = st.text_input("名称 *", placeholder="合同范本知识库")
        desc = st.text_area("描述", placeholder="用途说明...")
        tags = st.text_input("标签(逗号分隔)", placeholder="合同,法律")

    with c2:
        files = st.file_uploader(
            "上传文件", type=["txt", "docx", "doc"], accept_multiple_files=True
        )
        if files:
            st.info(
                f"已选 {len(files)} 个文件，共 {sum(f.size for f in files)/1024:.1f} KB"
            )

    if st.button("🚀 创建知识库并构建向量库", type="primary"):
        if not name:
            st.error("请输入名称")
        elif not files:
            st.error("请上传文件")
        else:
            with st.status("处理中...", expanded=True) as status:
                kb_id, errors = create_knowledge_base_full(
                    kb_manager=kb_manager,
                    name=name,
                    uploaded_files=files,
                    description=desc,
                    tags=[t.strip() for t in tags.split(",") if t.strip()],
                    status_callback=lambda m: status.write(m),
                )
                status.update(label="完成", state="complete")

            if kb_id:
                st.success(f"✅ 知识库「{name}」创建成功！")
                st.rerun()
            else:
                for e in errors:
                    st.error(e)

# ==================== Tab3: 知识图谱 ====================
with tab3:
    st.markdown("### 🌐 知识图谱可视化与管理")

    # 选择知识库
    kbs_with_data = [
        kb for kb in kb_manager.list_kbs() if kb_manager.has_graph_data(kb.id)
    ]

    if not kbs_with_data:
        st.info("📭 暂无知识图谱，请先在「文档检索」页面构建")
    else:
        # 多选
        cols = st.columns(min(len(kbs_with_data), 4))
        selected_ids = []
        for i, kb in enumerate(kbs_with_data):
            with cols[i % len(cols)]:
                if st.checkbox(
                    f"{kb.name}\n({kb.entity_count}实体)", key=f"sel_{kb.id}"
                ):
                    selected_ids.append(kb.id)

        if selected_ids:
            # 合并图谱
            graphs = []
            for kid in selected_ids:
                data = kb_manager.load_graph(kid)
                if data:
                    graphs.append(KnowledgeBaseSerializer.dict_to_graph(data))

            merged = KnowledgeBaseSerializer.merge_graphs(graphs) if graphs else None

            if merged:
                # 统计
                display_graph_stats(merged)
                # st.markdown("---")

                # 可视化控制
                c1, c2, c3, c4 = st.columns([0.8, 0.4, 1.5, 0.3])
                with c1:
                    height = st.slider("高度", 400, 800, 500)
                with c2:
                    show_labels = st.checkbox(
                        "显示关系标签",
                        True,
                        help="在图谱连线上显示关系的类型文字（如'属于'、'包含'等）",
                    )
                    physics = st.checkbox(
                        "物理引擎",
                        True,
                        help="启用物理模拟布局，关闭后节点位置固定，适合手动调整后的精细查看",
                    )
                with c3:
                    types = list(set(e.entity_type for e in merged.entities.values()))
                    # 获取颜色映射
                    entity_colors = KnowledgeGraphVisualizer.ENTITY_COLORS

                    # 按颜色排序类型，保持一致的显示顺序
                    sorted_types = sorted(
                        types, key=lambda t: (entity_colors.get(t, "#CCCCCC"), t)
                    )

                    # 下拉多选框筛选类型
                    sel_types = st.multiselect(
                        "筛选类型",
                        sorted_types,
                        default=sorted_types,
                        format_func=lambda x: f"{x}",
                    )

                    # 显示颜色图例
                    legend_html = ""
                    for t in sel_types:
                        color = entity_colors.get(t, "#CCCCCC")
                        legend_html += f"<span style='display:inline-block;margin:2px 8px 2px 0;'><span style='display:inline-block;width:12px;height:12px;background:{color};border-radius:50%;margin-right:4px;vertical-align:middle;'></span><span style='vertical-align:middle;font-size:12px;'>{t}</span></span>"
                    if legend_html:
                        st.markdown(
                            f"<div style='margin-top:5px;'>{legend_html}</div>",
                            unsafe_allow_html=True,
                        )
                with c4:
                    use_3d = st.toggle(
                        "🌐3D视图",
                        value=False,
                        help="切换到3D球状视图，左键旋转、右键平移、滚轮缩放，点击节点查看详情",
                    )
                    if use_3d:
                        st.caption("🖱️ 拖拽旋转，滚轮缩放")

                # 渲染可视化（传入筛选后的类型和3D选项）
                html = render_graph_visualization(
                    merged,
                    height,
                    show_labels,
                    physics,
                    filter_types=sel_types,
                    use_3d=use_3d,
                )
                st.components.v1.html(html, height=height + 80)
                st.caption(
                    "💡 拖拽调整位置，滚轮缩放，双击节点查看详情"
                    if not use_3d
                    else "💡 3D视图：左键旋转，右键平移，滚轮缩放，点击节点查看详情"
                )

                # st.markdown("---")

                # 数据管理
                dt1, dt2, dt3 = st.tabs(["📌 实体", "🔗 关系", "✏️ 编辑"])

                with dt1:
                    display_entity_table(merged)

                with dt2:
                    display_relation_table(merged)

                with dt3:
                    entity_names = list(merged.entities.keys())
                    if entity_names:
                        sel = st.selectbox("选择实体", entity_names)
                        ent = merged.entities[sel]

                        nc1, nc2 = st.columns(2)
                        with nc1:
                            new_type = st.selectbox(
                                "类型",
                                ENTITY_TYPES,
                                index=(
                                    ENTITY_TYPES.index(ent.entity_type)
                                    if ent.entity_type in ENTITY_TYPES
                                    else 0
                                ),
                            )
                        with nc2:
                            new_mentions = st.number_input(
                                "次数", 1, 1000, ent.mentions
                            )

                        new_desc = st.text_area("描述", ent.description, height=80)

                        bc1, bc2 = st.columns(2)
                        with bc1:
                            if st.button("💾 保存", type="primary"):
                                edit_entity(
                                    merged, sel, new_type, new_desc, new_mentions
                                )
                                kb_manager.save_graph(
                                    selected_ids[0],
                                    KnowledgeBaseSerializer.graph_to_dict(merged),
                                )
                                st.success("已保存")
                                st.rerun()
                        with bc2:
                            if st.button("🗑️ 删除"):
                                delete_entity(merged, sel)
                                kb_manager.save_graph(
                                    selected_ids[0],
                                    KnowledgeBaseSerializer.graph_to_dict(merged),
                                )
                                st.success("已删除")
                                st.rerun()

                        # st.markdown("---")
                        st.markdown("#### 添加实体")
                        ac1, ac2, ac3 = st.columns(3)
                        with ac1:
                            add_name = st.text_input("名称")
                        with ac2:
                            add_type = st.selectbox(
                                "类型", ENTITY_TYPES[:8], key="add_t"
                            )
                        with ac3:
                            add_desc = st.text_input("描述", key="add_d")

                        if st.button("➕ 添加实体"):
                            if add_name and add_entity(
                                merged, add_name, add_type, add_desc
                            ):
                                kb_manager.save_graph(
                                    selected_ids[0],
                                    KnowledgeBaseSerializer.graph_to_dict(merged),
                                )
                                st.success(f"已添加: {add_name}")
                                st.rerun()
                            else:
                                st.warning("名称已存在或为空")

                        st.markdown("#### 添加关系")
                        if len(entity_names) >= 2:
                            rc1, rc2, rc3 = st.columns(3)
                            with rc1:
                                r_src = st.selectbox(
                                    "源实体", entity_names, key="r_src"
                                )
                            with rc2:
                                r_type = st.selectbox(
                                    "关系", RELATION_TYPES, key="r_type"
                                )
                            with rc3:
                                r_tgt = st.selectbox(
                                    "目标实体", entity_names, key="r_tgt"
                                )

                            if st.button("➕ 添加关系"):
                                if add_relation(merged, r_src, r_tgt, r_type):
                                    kb_manager.save_graph(
                                        selected_ids[0],
                                        KnowledgeBaseSerializer.graph_to_dict(merged),
                                    )
                                    st.success(f"已添加: {r_src} → {r_tgt}")
                                    st.rerun()
                                else:
                                    st.warning("添加失败")
                    else:
                        st.info("暂无实体")

# 页脚
# st.markdown("---")
st.caption("💡 知识库数据永久存储在本地，下次登录仍可使用")
