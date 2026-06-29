import streamlit as st

from src.config import PROJECT_TITLE, SUPPORTED_DOMAINS

st.set_page_config(page_title=PROJECT_TITLE, page_icon="🚀", layout="wide")

st.title(PROJECT_TITLE)
st.caption("Multi-agent startup idea generator with RAG, LangChain, LangGraph, and Supabase")

with st.sidebar:
    st.header("Project Setup")
    selected_domain = st.selectbox("Select startup domain", SUPPORTED_DOMAINS)
    st.write("Use this panel to drive the idea generation workflow.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input")
    startup_goal = st.text_area(
        "Describe what you want to build",
        placeholder="Example: A Healthcare AI startup for patient triage",
        height=140,
    )
    run_workflow = st.button("Generate Startup Report", type="primary")

with col2:
    st.subheader("Output Preview")
    if run_workflow:
        st.info(f"Selected domain: {selected_domain}")
        st.success("Workflow scaffold is ready. Next step: connect LangGraph nodes and RAG retrieval.")
        st.write(startup_goal or "No description provided.")
    else:
        st.write("Your final report will appear here after connecting the workflow.")
