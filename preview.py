"""Streamlit preview wrapper — embeds the React frontend via iframe."""
import streamlit as st

st.set_page_config(page_title="Run Season Command", layout="wide")

st.markdown(
    """
    <style>
        .stAppHeader, header, footer, #MainMenu {display: none !important;}
        .block-container {padding: 0 !important; max-width: 100% !important;}
        iframe {border: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.components.v1.iframe("http://localhost:8000", height=900, scrolling=True)
