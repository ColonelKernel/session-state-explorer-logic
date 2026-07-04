import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = "src/logic_session_evidence_explorer/app.py"


@pytest.fixture(scope="module")
def demo_app():
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    # Skip descriptor extraction for speed; the UI paths are identical.
    at.sidebar.checkbox[0].set_value(False)
    next(b for b in at.button if b.label == "Build demo session").click()
    at.run()
    assert not at.exception
    return at


def test_evidence_meter_renders(demo_app):
    assert any("display:flex;height:14px" in str(m.value) for m in demo_app.markdown)


def test_highlight_takes_effect_in_same_frame(demo_app):
    at = demo_app
    hl = next(b for b in at.button if str(b.label) == "Highlight in graph")
    hl.click()
    at.run()
    # on_click runs before the script re-executes, so the click's own frame
    # must already show the highlight caption and the Clear button.
    assert at.session_state["highlight_ids"]
    assert any("Highlighting evidence for" in str(c.value) for c in at.caption)
    assert any(str(b.label) == "Clear highlight" for b in at.button)


def test_clear_highlight_takes_effect_in_same_frame(demo_app):
    at = demo_app
    clear = next(b for b in at.button if str(b.label) == "Clear highlight")
    clear.click()
    at.run()
    assert at.session_state["highlight_ids"] == []
    assert not any("Highlighting evidence for" in str(c.value) for c in at.caption)


def test_rebuilding_session_drops_stale_highlight(demo_app):
    at = demo_app
    hl = next(b for b in at.button if str(b.label) == "Highlight in graph")
    hl.click()
    at.run()
    assert at.session_state["highlight_ids"]
    next(b for b in at.button if b.label == "Build demo session").click()
    at.run()
    # A rebuilt session reuses the same id sequence for different nodes; a
    # surviving highlight would silently point at the wrong evidence.
    assert at.session_state["highlight_ids"] == []
