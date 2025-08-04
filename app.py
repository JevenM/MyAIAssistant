import streamlit as st
import io, os
from PIL import Image
from pydantic import BaseModel
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import HumanMessage, AIMessage
from langchain_community.utilities.searchapi import SearchApiAPIWrapper
from langchain.memory import ConversationBufferMemory
import toml
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda


# st.title("AI聊天机器人")
# st.header("by--毛毛小橙子")


with st.sidebar:
    st.title("你好 毛毛小橙子")
    # st.page_link("pages/history_item.py", label="history_item", icon="1️⃣")

    # st.page_link("pages/page_2.py", label="Page 2", icon="2️⃣", disabled=True)
    # st.page_link("http://www.google.com", label="Google", icon="🌎")
    # 设置一个可点击打开的展开区域
    with st.expander("🤓找到我的方式"):
        # 本地图片无法直接加载，需先将图片读取加载为bytes流，然后才能正常在streamlit中显示
        image_path = r"E:\\Desktop\\微信图片_20250803180325.jpg"
        image = Image.open(image_path)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG")
        st.image(image_bytes, caption="AI毛毛小橙子的微信", use_container_width=True)


def page2():
    st.title("Second page")
    st.set_page_config(layout="wide")

    # 真正内容放这里，相当于 container 内部
    with st.container(height=500):
        for i in range(50):
            st.write(f"这是一条内容 {i+1}")
    prompt = st.chat_input("您好，请问有什么可以帮助您的吗？")
    st.stop()


def page1():
    # st.html("<h1 style='text-align: center; color: black; font-weight: normal'>11</h1>")
    st.header("今天想聊点什么？")


def history_item():
    st.title("历史记录")
    st.write("这里展示聊天记录。")
    st.json(st.session_state.messages)
    st.stop()


pg = st.navigation(
    [
        st.Page(page1, title="First page", icon="🔥"),
        st.Page(page2, title="Second page", icon=":material/favorite:"),
        st.Page(history_item, title="历史记录", icon="📜"),
    ],
    position="sidebar",  # "sidebar"
)
pg.run()

config = toml.load("./.streamlit/secrets.toml")

# os.environ["DASHSCOPE_API_KEY"] =
model = ChatTongyi(
    model_name="qwen-max",
    streaming=True,
    dashscope_api_key=config["keys"]["dashscope_api_key"],
)

memory_key = "history"

if "messages" not in st.session_state:
    st.session_state.messages = []
    # 初始化聊天记录
    # st.session_state.memory = ConversationBufferMemory(memory_key="chat_history")

if "online" not in st.session_state:
    st.session_state.online = False


class Message(BaseModel):
    content: str
    role: str


def to_message_placeholder(messages):
    return [
        (
            AIMessage(content=message["content"])
            if message["role"] == "ai"
            else HumanMessage(content=message["content"])
        )
        for message in messages
    ]


# left, right = st.columns([0.7, 0.3])

# container_l = left.container()
# 首先在左边最上面展示聊天记录
con = st.container(key="message_con", height=500)
with con:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

# 设置搜索 API KEY # 从 https://www.searchapi.io 获取
# os.environ["SEARCHAPI_API_KEY"] = ( "" )

search = SearchApiAPIWrapper(
    engine="baidu", searchapi_api_key=config["keys"]["searchapi_api_key"]
)

# 定义 LCEL Chain
# Step 1: 用户输入传给 SearchAPI
search_chain = RunnableLambda(
    lambda x: {
        "context": search.run(x["input"]) if st.session_state.online else "",
        "input": x["input"],
        "history": to_message_placeholder(x["messages"]),
    }
)

if st.session_state.online:
    # st.write("Feature activated!")
    st.session_state.online = True
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name=memory_key),
            # ("human", "{input}"),
            (
                "human",
                "你是一个聪明的大语言模型，下面是我从互联网搜索的结果：{context}\n\n请基于这些信息回答这个问题\n:{input}",
            ),
        ]
    )
else:
    # st.write("Feature deactivated!")
    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name=memory_key),
            ("human", "{input}"),
        ]
    )


chain = search_chain | prompt | model | StrOutputParser()


col1, col2 = st.columns([0.9, 0.1], vertical_alignment="bottom")

if pt := st.chat_input("您好，请问有什么可以帮助您的吗？"):
    st.session_state.messages.append(Message(content=pt, role="human").dict())
    # with container_l:
    with st.chat_message("human"):
        st.write(pt)

    with st.chat_message("ai"):
        # import io, sys

        # 捕捉 stdout（用于 verbose）
        # verbose_output = io.StringIO()
        # sys_stdout = sys.stdout
        # sys.stdout = verbose_output

        try:
            res = chain.stream(
                {"input": pt, "messages": st.session_state.messages},
                config={"verbose": True},
                # config={"callbacks": [ConsoleCallbackHandler()]},
            )
            # print("verbose: ", res)
            response = st.write_stream(res)
        except Exception as e:
            response = f"发生错误: {e}"
        # finally:
        # 恢复 stdout
        # sys.stdout = sys_stdout
        # st.subheader("🧾 执行过程（verbose）:")
        # st.code(verbose_output.getvalue())
        # st.subheader("✅ 最终生成结果:")
        # st.success(res)
        # print("AI response:", response)
    st.session_state.messages.append(Message(content=response, role="ai").dict())

# container_r = right.container()
# container_r.json(st.session_state.messages)
with col1:
    st.caption("A caption with _italics_ :blue[colors] and emojis :sunglasses:")
with col2:
    st.session_state.online = st.toggle("网页搜索", value=st.session_state.online)
