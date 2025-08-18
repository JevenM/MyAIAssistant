import streamlit as st


if "logged_in_user" not in st.session_state or not st.session_state.logged_in_user:
    st.stop()

st.title("个人信息页")

st.header(f"{st.session_state.logged_in_user}")

st.stop()
