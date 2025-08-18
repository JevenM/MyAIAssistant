import streamlit as st

from login import login_and_register

if "logged_in_user" not in st.session_state or not st.session_state.logged_in_user:
    # login_and_register()
    # st.warning("请先登录后再使用本页面~")
    st.stop()
else:
    st.header(f"今天想聊点什么？")
# st.stop()
