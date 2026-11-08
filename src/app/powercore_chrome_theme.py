"""Inject PowerCore Chrome (near-black) into Streamlit.

Tokens live in static/powercore_chrome_streamlit.css — mirror of
powercore-ops/design/powercore-chrome.tokens.css for the second-brain UI.
"""
from __future__ import annotations

from pathlib import Path

_CSS_PATH = Path(__file__).resolve().parent / "static" / "powercore_chrome_streamlit.css"
_injected = False


def load_chrome_css() -> str:
    return _CSS_PATH.read_text(encoding="utf-8")


def inject_powercore_chrome(st) -> None:
    """Inject every run — Streamlit rebuilds the DOM on each script pass."""
    global _injected
    css = load_chrome_css()
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
    _injected = True
