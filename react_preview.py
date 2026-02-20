"""Render the React SPA build inside the platform preview.

This script is executed by Streamlit (via serve.py). It reads the
compiled React assets, inlines them into a single HTML blob, and
renders it with st.components.v1.html(). The surrounding Streamlit
chrome is hidden via CSS so the user sees only the React app.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Run Season Command",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide all Streamlit UI chrome
st.markdown(
    """<style>
    #MainMenu, header, footer,
    [data-testid="stSidebar"],
    [data-testid="stDecoration"],
    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"] { display: none !important; }
    .stApp { padding: 0 !important; }
    section.main { padding: 0 !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    iframe { border: none !important; }
    </style>""",
    unsafe_allow_html=True,
)

DIST = Path("frontend/dist")


@st.cache_resource
def build_html() -> str:
    """Read the React build and inline all assets into one HTML string."""
    html = (DIST / "index.html").read_text()

    # Inline CSS
    for m in re.finditer(
        r'<link[^>]+href="(/assets/[^"]+\.css)"[^>]*/?>',
        html,
    ):
        css = (DIST / m.group(1).lstrip("/")).read_text()
        html = html.replace(m.group(0), f"<style>{css}</style>")

    # Inline JS
    for m in re.finditer(
        r'<script[^>]+src="(/assets/[^"]+\.js)"[^>]*></script>',
        html,
    ):
        js = (DIST / m.group(1).lstrip("/")).read_text()
        html = html.replace(
            m.group(0),
            f'<script type="module">{js}</script>',
        )

    return html


components.html(build_html(), height=900, scrolling=True)
