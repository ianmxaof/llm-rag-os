"""PowerCore Chrome CSS asset must load for Streamlit shell."""
from pathlib import Path

from src.app.powercore_chrome_theme import load_chrome_css


def test_chrome_css_has_near_black_tokens():
    css = load_chrome_css()
    assert "--pc-bg: #0a0a0b" in css
    assert "--pc-accent-cyan: #22d3ee" in css
    assert 'font-family: var(--pc-font-ui)' in css or "--pc-font-ui:" in css
    assert "Inter" in css


def test_chrome_css_file_exists():
    p = Path(__file__).resolve().parents[1] / "src" / "app" / "static" / "powercore_chrome_streamlit.css"
    assert p.is_file()
