import pytest

from logic_session_evidence_explorer import session_builder, stem_scanner, utils
from logic_session_evidence_explorer.models import SessionEvidence
from logic_session_evidence_explorer.visualization import (
    MAX_LABEL_CHARS,
    OBSERVABILITY_ORDER,
    layered_positions,
    truncate_label,
)


def _session():
    utils.reset_ids()
    names = ["01_Drums.wav", "02_Bass.wav", "05_Lead_Vocal.wav", "Stereo_Mix_Bounce.wav"]
    files = [stem_scanner.ScannedFile(file_name=n) for n in names]
    audio = stem_scanner.scan_files(files)
    session = SessionEvidence(session_name="VizTest", audio_files=audio)
    return session_builder.finalize_session(session, with_descriptors=False)


def test_truncate_label_short_names_untouched():
    assert truncate_label("Lead Vocal") == "Lead Vocal"


def test_truncate_label_long_names_ellipsized():
    long = "Add channel-strip notes to improve DAW-state interpretability."
    out = truncate_label(long)
    assert len(out) <= MAX_LABEL_CHARS
    assert out.endswith("…")
    # A "Track: "-prefixed demo track name must fit untruncated.
    assert truncate_label("Track: Backing Vocals Bounce") == "Track: Backing Vocals Bounce"


def test_layered_positions_column_order():
    from logic_session_evidence_explorer.graph_builder import build_graph_export

    export = build_graph_export(_session())
    positions = layered_positions(export.nodes)
    # Every node gets a position.
    assert set(positions) == {n["id"] for n in export.nodes}
    # Column x increases with observability order: any observed node sits
    # left of any hidden node.
    by_class = {}
    for n in export.nodes:
        by_class.setdefault(n["observability"], []).append(positions[n["id"]][0])
    present = [k for k in OBSERVABILITY_ORDER if k in by_class]
    xs = [max(by_class[k]) for k in present]
    assert xs == sorted(xs)
    # Nodes within a class share a column.
    for k, column_xs in by_class.items():
        assert len(set(column_xs)) == 1


def test_pyvis_html_freezes_physics_and_truncates():
    pytest.importorskip("pyvis")
    html = __import__(
        "logic_session_evidence_explorer.visualization", fromlist=["build_pyvis_html"]
    ).build_pyvis_html(_session())
    assert "stabilizationIterationsDone" in html
    # Full recommendation titles are too long for node labels; the truncated
    # form (with ellipsis, JSON-escaped by pyvis) must be what is displayed.
    assert "…" in html or "\\u2026" in html


def test_pyvis_layered_layout_has_fixed_positions_no_physics_freeze():
    pytest.importorskip("pyvis")
    from logic_session_evidence_explorer.visualization import build_pyvis_html

    html = build_pyvis_html(_session(), layout="layered")
    assert "stabilizationIterationsDone" not in html
    assert '"x":' in html and '"y":' in html
    # No physics means no stabilisation auto-fit: the explicit fit must be
    # injected or the default view renders zoomed-in.
    assert "network.fit()" in html


def test_dark_fill_nodes_get_white_labels():
    pytest.importorskip("pyvis")
    import json as _json
    import re

    from logic_session_evidence_explorer.models import AudioDescriptorSet
    from logic_session_evidence_explorer.visualization import build_pyvis_html

    session = _session()
    first = session.audio_files[0]
    desc = AudioDescriptorSet(id="descriptor_test", source_id=first.id,
                              file_name=first.file_name)
    first.descriptor_id = desc.id
    session.descriptors.append(desc)

    html = build_pyvis_html(session)
    nodes_json = re.search(r"nodes = new vis.DataSet\((\[.*?\])\);", html, re.S)
    assert nodes_json, "could not locate nodes payload in pyvis HTML"
    nodes = _json.loads(nodes_json.group(1))
    by_id = {n["id"]: n for n in nodes}
    # pyvis silently overwrites per-node fonts when a constructor-level
    # font_color is set — this asserts the white font actually survives.
    assert by_id["descriptor_test"]["font"]["color"] == "#ffffff"
    assert by_id[first.id]["font"]["color"] == "#222222"


def test_pyvis_highlight_enlarges_nodes():
    pytest.importorskip("pyvis")
    from logic_session_evidence_explorer.visualization import build_pyvis_html

    session = _session()
    target = session.audio_files[0].id
    html = build_pyvis_html(session, highlight_ids=[target])
    assert '"borderWidth": 4' in html
