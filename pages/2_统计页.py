import streamlit as st
import pandas as pd
import altair as alt
from collections import defaultdict
from login import require_login

st.set_page_config(page_title="统计分析", page_icon="📈")

# ========== 统一登录检查 ==========
require_login()

user = st.session_state.logged_in_user
records = st.session_state.records.get(user, [])

st.title("📊 账单统计分析")

if not records:
    st.info("暂无记录，快去添加记账信息吧！")
    st.stop()

df = pd.DataFrame(records)

st.subheader("💰 收支比例分析")
total_by_type = df.groupby("类型")["金额"].sum().reset_index()

pie_chart = (
    alt.Chart(total_by_type)
    .mark_arc(innerRadius=50)
    .encode(
        theta=alt.Theta(field="金额", type="quantitative"),
        color=alt.Color(field="类型", type="nominal"),
        tooltip=["类型", "金额"],
    )
)

st.altair_chart(pie_chart, use_container_width=True)

st.subheader("📂 分类占比分析")
selected_type = st.radio("选择查看类型", ["支出", "收入"], horizontal=True)

filtered_df = df[df["类型"] == selected_type]
if filtered_df.empty:
    st.info(f"没有 {selected_type} 的记录")
else:
    category_sum = filtered_df.groupby("分类")["金额"].sum().reset_index()

    bar_chart = (
        alt.Chart(category_sum)
        .mark_bar()
        .encode(
            x=alt.X("分类", sort="-y", axis=alt.Axis(labelAngle=0)),
            y="金额",
            tooltip=["分类", "金额"],
        )
        .properties(height=300)
    )

    st.altair_chart(bar_chart, use_container_width=True)

st.subheader("📅 每日收支趋势图")

df["日期"] = pd.to_datetime(df["日期"])
df_recent = df[df["日期"] >= pd.Timestamp.now() - pd.Timedelta(days=30)]

if df_recent.empty:
    st.info("近30天暂无记录，无法绘制趋势图~")
else:
    trend = df_recent.groupby(["日期", "类型"])["金额"].sum().reset_index()

    line_chart = (
        alt.Chart(trend)
        .mark_line(point=True)
        .encode(
            x="日期:T", y="金额:Q", color="类型:N", tooltip=["日期", "类型", "金额"]
        )
        .properties(height=300)
    )

    st.altair_chart(line_chart, use_container_width=True)
st.stop()
