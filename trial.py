import streamlit as st
import time
from login import require_login

# ========== 页面配置 ==========
st.set_page_config(
    page_title="功能体验 - 小橙子智能助手",
    page_icon="🎯",
    layout="wide",
)

# ========== 统一登录检查 ==========
require_login()

# ========== 自定义样式 ==========
st.markdown("""
<style>
    .demo-card {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .feature-tag {
        display: inline-block;
        background: #667eea;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin-right: 0.3rem;
    }
</style>
""", unsafe_allow_html=True)

# ========== 页面标题 ==========
st.markdown("# 🎯 功能体验中心")
st.markdown("在这里体验小橙子智能助手的各项核心功能！")
st.markdown("---")

# ========== 功能演示区 ==========
tab1, tab2, tab3, tab4 = st.tabs(["💬 对话演示", "📝 文本处理", "🔢 计算工具", "🎨 格式转换"])

# ========== 对话演示 ==========
with tab1:
    st.markdown("### 💬 智能对话演示")
    st.markdown("体验智能对话的核心能力（模拟演示）")

    # 预设对话示例
    demo_questions = [
        ("你好，请介绍一下你自己", "你好！我是小橙子智能助手，一个基于大语言模型构建的智能对话伙伴。我可以回答问题、进行知识问答、帮助分析文档，还能帮你记账和做统计分析。有什么我可以帮助你的吗？"),
        ("今天天气怎么样？", "抱歉，我无法获取实时天气信息。不过你可以开启联网搜索功能，我就能帮你查询最新的天气情况了！"),
        ("帮我写一首关于春天的诗", """春风轻拂柳丝长，
桃花朵朵映红妆。
燕子归来寻旧巢，
绿草如茵满庭芳。

这首诗描绘了春天的美好景象：春风、桃花、燕子、绿草，构成了一幅生机勃勃的春日画卷。"""),
        ("用Python写一个冒泡排序", """```python
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

# 使用示例
numbers = [64, 34, 25, 12, 22, 11, 90]
sorted_numbers = bubble_sort(numbers)
print(f"排序结果: {sorted_numbers}")
```

冒泡排序的时间复杂度为 O(n²)，适合小规模数据排序。"""),
    ]

    selected_q = st.selectbox(
        "选择演示问题",
        options=[q[0] for q in demo_questions],
        index=0
    )

    if st.button("🚀 开始演示", use_container_width=True):
        # 找到对应的回答
        answer = next((a for q, a in demo_questions if q == selected_q), "")

        # 模拟打字效果
        with st.chat_message("user"):
            st.write(selected_q)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            for chunk in answer.split("\n"):
                if full_response:
                    full_response += "\n" + chunk
                else:
                    full_response = chunk
                message_placeholder.markdown(full_response)
                time.sleep(0.1)

            message_placeholder.markdown(full_response)

# ========== 文本处理 ==========
with tab2:
    st.markdown("### 📝 文本处理工具")

    text_input = st.text_area(
        "输入文本",
        placeholder="在这里输入需要处理的文本...",
        height=150
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📊 统计字数", use_container_width=True):
            if text_input:
                st.info(f"""
                **统计结果**
                - 总字符数：{len(text_input)}
                - 中文字数：{sum(1 for c in text_input if '一' <= c <= '鿿')}
                - 英文字数：{sum(1 for c in text_input if c.isalpha() and c.isascii())}
                - 数字个数：{sum(1 for c in text_input if c.isdigit())}
                - 空格个数：{text_input.count(' ')}
                """)
            else:
                st.warning("请先输入文本")

    with col2:
        if st.button("🔄 大小写转换", use_container_width=True):
            if text_input:
                st.code(text_input.upper(), language="text")
            else:
                st.warning("请先输入文本")

    with col3:
        if st.button("✂️ 去除空格", use_container_width=True):
            if text_input:
                st.code(text_input.replace(" ", "").replace("\n", ""), language="text")
            else:
                st.warning("请先输入文本")

    # 文本分析
    st.markdown("#### 📈 文本分析")
    if text_input:
        # 词频统计（简单版）
        import re
        words = re.findall(r'[一-鿿]+|[a-zA-Z]+', text_input)
        if words:
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1

            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]

            st.markdown("**高频词统计（前10）：**")
            for word, count in sorted_words:
                st.markdown(f"- `{word}`: {count} 次")

# ========== 计算工具 ==========
with tab3:
    st.markdown("### 🔢 计算工具")

    calc_col1, calc_col2 = st.columns(2)

    with calc_col1:
        st.markdown("#### 📐 基础计算器")
        expression = st.text_input("输入数学表达式", placeholder="例如：2 + 3 * 4")
        if st.button("计算", key="calc_basic"):
            try:
                result = eval(expression)
                st.success(f"结果：{result}")
            except Exception as e:
                st.error(f"计算错误：{e}")

        st.markdown("#### 💰 百分比计算")
        base_num = st.number_input("基数", value=100.0)
        percent = st.number_input("百分比 (%)", value=10.0)
        if st.button("计算百分比", key="calc_percent"):
            result = base_num * percent / 100
            st.info(f"{base_num} 的 {percent}% = {result}")

    with calc_col2:
        st.markdown("#### 📊 单位换算")
        convert_type = st.selectbox(
            "选择换算类型",
            ["长度", "重量", "温度"]
        )

        if convert_type == "长度":
            length_val = st.number_input("输入数值", value=1.0)
            length_unit = st.selectbox("单位", ["米", "厘米", "英寸", "英尺"])
            conversions = {
                "米": (1, "米"),
                "厘米": (0.01, "米"),
                "英寸": (0.0254, "米"),
                "英尺": (0.3048, "米")
            }
            if st.button("换算", key="conv_length"):
                meters = length_val * conversions[length_unit][0]
                st.info(f"""
                换算结果：
                - {meters:.4f} 米
                - {meters * 100:.4f} 厘米
                - {meters / 0.0254:.4f} 英寸
                - {meters / 0.3048:.4f} 英尺
                """)

        elif convert_type == "重量":
            weight_val = st.number_input("输入数值", value=1.0)
            weight_unit = st.selectbox("单位", ["千克", "克", "磅", "盎司"])
            conversions = {
                "千克": (1, "千克"),
                "克": (0.001, "千克"),
                "磅": (0.453592, "千克"),
                "盎司": (0.0283495, "千克")
            }
            if st.button("换算", key="conv_weight"):
                kg = weight_val * conversions[weight_unit][0]
                st.info(f"""
                换算结果：
                - {kg:.4f} 千克
                - {kg * 1000:.4f} 克
                - {kg / 0.453592:.4f} 磅
                - {kg / 0.0283495:.4f} 盎司
                """)

        elif convert_type == "温度":
            temp_val = st.number_input("输入数值", value=0.0)
            temp_unit = st.selectbox("单位", ["摄氏度", "华氏度", "开尔文"])
            if st.button("换算", key="conv_temp"):
                if temp_unit == "摄氏度":
                    c = temp_val
                elif temp_unit == "华氏度":
                    c = (temp_val - 32) * 5 / 9
                else:  # 开尔文
                    c = temp_val - 273.15
                st.info(f"""
                换算结果：
                - {c:.2f} 摄氏度
                - {c * 9 / 5 + 32:.2f} 华氏度
                - {c + 273.15:.2f} 开尔文
                """)

# ========== 格式转换 ==========
with tab4:
    st.markdown("### 🎨 格式转换工具")

    format_col1, format_col2 = st.columns(2)

    with format_col1:
        st.markdown("#### 📋 JSON 格式化")
        json_input = st.text_area("输入 JSON", height=100, placeholder='{"name": "test"}')
        if st.button("格式化 JSON", key="format_json"):
            try:
                import json
                parsed = json.loads(json_input)
                st.code(json.dumps(parsed, indent=2, ensure_ascii=False), language="json")
            except Exception as e:
                st.error(f"JSON 解析错误：{e}")

    with format_col2:
        st.markdown("#### 🔗 列表处理")
        list_input = st.text_area(
            "输入列表（每行一项）",
            height=100,
            placeholder="苹果\n香蕉\n橙子"
        )
        list_action = st.selectbox(
            "操作",
            ["去重", "排序", "反转", "统计数量"]
        )
        if st.button("处理", key="process_list"):
            if list_input:
                items = list_input.strip().split("\n")
                if list_action == "去重":
                    result = list(dict.fromkeys(items))
                    st.code("\n".join(result), language="text")
                elif list_action == "排序":
                    result = sorted(items)
                    st.code("\n".join(result), language="text")
                elif list_action == "反转":
                    result = items[::-1]
                    st.code("\n".join(result), language="text")
                elif list_action == "统计数量":
                    st.info(f"总数量：{len(items)} 项")
            else:
                st.warning("请先输入内容")

# ========== 底部提示 ==========
st.markdown("---")
st.markdown("💡 **提示**：这只是功能演示，完整功能请前往首页开始聊天！")
