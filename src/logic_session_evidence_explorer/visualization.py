"""Graph visualisation helpers (PyVis primary, Plotly fallback).

The visualisation colour-codes nodes by *observability* so that observed
evidence, inferred state, user annotations and hidden-state markers are
visually distinct — the core interpretability affordance of the tool.

Two layouts are offered:

- ``force``: force-directed, with physics frozen once the layout stabilises
  so the graph holds still (important for screen recordings).
- ``layered``: nodes are columned left-to-right by observability class
  (observed → inferred → annotation → hidden → derived), making the
  evidence-to-hidden gradient readable at a glance.
"""

from __future__ import annotations

from .graph_builder import build_graph_export
from .models import SessionEvidence

# Colour per observability class (used by both backends and the UI legend).
OBSERVABILITY_COLORS = {
    "observed": "#2E86DE",     # blue
    "inferred": "#27AE60",     # green
    "annotation": "#F39C12",   # orange
    "hidden": "#C0392B",       # red
    "derived": "#8E44AD",      # purple
    "unknown": "#7F8C8D",      # grey
}

# Left-to-right column order for the layered layout.
OBSERVABILITY_ORDER = ["observed", "inferred", "annotation", "hidden", "derived"]

TYPE_SHAPES = {
    "session": "star",
    "audio_evidence": "dot",
    "mixdown": "square",
    "reference_track": "triangle",
    "inferred_track": "dot",
    "midi_file": "diamond",
    "midi_track": "diamond",
    "musicxml_file": "diamond",
    "musicxml_part": "diamond",
    "channel_strip_note": "box",
    "plugin_note": "box",
    "send_note": "box",
    "bus_note": "box",
    "descriptor_set": "ellipse",
    "stem_sum_reconciliation": "database",
    "reference_comparison": "database",
    "hidden_state_marker": "triangleDown",
    "recommendation": "hexagon",
}

LEGEND = [
    ("Session", "observed"),
    ("Audio evidence", "observed"),
    ("Inferred track", "inferred"),
    ("Mixdown", "observed"),
    ("Reference", "observed"),
    ("MIDI", "observed"),
    ("MusicXML", "observed"),
    ("Channel-strip note", "annotation"),
    ("Descriptor (ellipse)", "derived"),
    ("Hidden state", "hidden"),
    ("Recommendation (hexagon)", "derived"),
]

# Sized so a "Track: "-prefixed demo track name still fits untruncated.
MAX_LABEL_CHARS = 28

# Injected after the vis.Network is constructed: freeze physics once the
# force layout has stabilised, so the graph does not jiggle on camera.
_FREEZE_PHYSICS_JS = (
    "network.once('stabilizationIterationsDone', function () {"
    " network.setOptions({physics: false}); });"
)
# With physics off (layered layout) there is no stabilisation event to
# trigger vis-network's auto-fit, so fit explicitly once drawn.
_FIT_VIEW_JS = "network.once('afterDrawing', function () { network.fit(); });"
_NETWORK_CTOR = "network = new vis.Network(container, data, options);"


def _color(node: dict) -> str:
    return OBSERVABILITY_COLORS.get(node.get("observability", "unknown"), "#7F8C8D")


def truncate_label(label: str, max_chars: int = MAX_LABEL_CHARS) -> str:
    """Shorten a node label for display; the full text lives in the tooltip."""

    label = label or ""
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1].rstrip() + "…"


def layered_positions(nodes: list[dict], *, column_gap: int = 260, row_gap: int = 90) -> dict[str, tuple[int, int]]:
    """Fixed (x, y) positions columning nodes by observability class.

    Columns run observed → inferred → annotation → hidden → derived; rows are
    vertically centred within each column.
    """

    columns: dict[str, list[dict]] = {k: [] for k in OBSERVABILITY_ORDER}
    for node in nodes:
        key = node.get("observability", "unknown")
        columns.setdefault(key, []).append(node)

    positions: dict[str, tuple[int, int]] = {}
    for col_index, key in enumerate(k for k in columns if columns[k]):
        members = columns[key]
        offset = (len(members) - 1) * row_gap / 2
        for row_index, node in enumerate(members):
            positions[node["id"]] = (col_index * column_gap, int(row_index * row_gap - offset))
    return positions


def filter_graph(export, *, show_descriptors=True, show_hidden=True, show_recommendations=True,
                 show_score=True, observability_only=None):
    """Return (nodes, edges) after applying UI filters.

    ``observability_only`` restricts to a single observability class when set
    (``"observed"`` / ``"inferred"`` / ``"annotation"`` / ``"hidden"`` /
    ``"derived"``).
    """

    hidden_types = set()
    if not show_descriptors:
        hidden_types.add("descriptor_set")
    if not show_hidden:
        hidden_types.add("hidden_state_marker")
    if not show_recommendations:
        hidden_types.add("recommendation")
    if not show_score:
        hidden_types.update({"midi_file", "midi_track", "musicxml_file", "musicxml_part"})

    nodes = []
    for n in export.nodes:
        if n["type"] in hidden_types:
            continue
        if observability_only and n.get("observability") != observability_only and n["type"] != "session":
            continue
        nodes.append(n)
    keep = {n["id"] for n in nodes}
    edges = [e for e in export.edges if e["source"] in keep and e["target"] in keep]
    return nodes, edges


def _node_tooltip(n: dict) -> str:
    bits = [n.get("label", "")]
    bits.append(f"type: {n['type']}")
    bits.append(f"observability: {n.get('observability')}")
    if n.get("role"):
        bits.append(f"role: {n['role']}")
    if n.get("confidence") is not None:
        bits.append(f"confidence: {n['confidence']}")
    if n.get("plugin_category"):
        bits.append(
            f"documented Logic stock plug-in ({n['plugin_category']}, "
            f"{n.get('plugin_generation', 'current')})"
        )
    if n.get("description"):
        bits.append(n["description"])
    return "\n".join(bits)


def build_pyvis_html(session: SessionEvidence, *, height: str = "650px",
                     layout: str = "force", highlight_ids: list[str] | None = None,
                     **filters) -> str:
    """Render the session graph to standalone PyVis HTML.

    ``layout`` is ``"force"`` (physics, frozen after stabilisation) or
    ``"layered"`` (fixed columns by observability class). ``highlight_ids``
    enlarges and outlines the given nodes — used to spotlight the evidence
    behind a recommendation. Raises if PyVis is absent.
    """

    from pyvis.network import Network

    export = build_graph_export(session)
    nodes, edges = filter_graph(export, **filters)
    highlight = set(highlight_ids or [])

    # No constructor-level font_color: pyvis would silently overwrite every
    # per-node font dict with it (Node.__init__ applies font_color last).
    net = Network(height=height, width="100%", directed=True, bgcolor="#ffffff")
    positions = {}
    if layout == "layered":
        positions = layered_positions(nodes)
        net.toggle_physics(False)
    else:
        net.barnes_hut(gravity=-8000, spring_length=120)

    # Shapes that draw the label INSIDE the node need a light font on our
    # dark (purple) fills to stay readable; below-node labels keep dark text.
    inside_label_dark_fills = {"descriptor_set", "stem_sum_reconciliation", "reference_comparison"}

    for n in nodes:
        kwargs: dict = {
            "label": truncate_label(n["label"]),
            "shape": TYPE_SHAPES.get(n["type"], "dot"),
            "title": _node_tooltip(n),
            "font": {"color": "#ffffff" if n["type"] in inside_label_dark_fills else "#222222"},
        }
        if n["id"] in highlight:
            kwargs["color"] = {"background": _color(n), "border": "#111111"}
            kwargs["borderWidth"] = 4
            kwargs["size"] = 28
        else:
            kwargs["color"] = _color(n)
        if n["id"] in positions:
            kwargs["x"], kwargs["y"] = positions[n["id"]]
        net.add_node(n["id"], **kwargs)
    for e in edges:
        net.add_edge(e["source"], e["target"], title=e["type"], arrows="to")

    try:
        html = net.generate_html(notebook=False)
    except TypeError:  # older pyvis
        html = net.generate_html()

    if _NETWORK_CTOR in html:
        inject = _FREEZE_PHYSICS_JS if layout == "force" else _FIT_VIEW_JS
        html = html.replace(_NETWORK_CTOR, _NETWORK_CTOR + "\n" + inject)
    return html


def build_plotly_figure(session: SessionEvidence, *, layout: str = "force",
                        highlight_ids: list[str] | None = None, **filters):
    """Render the session graph as a Plotly figure (fallback backend)."""

    import networkx as nx
    import plotly.graph_objects as go

    export = build_graph_export(session)
    nodes, edges = filter_graph(export, **filters)
    keep = {n["id"] for n in nodes}
    highlight = set(highlight_ids or [])

    if layout == "layered":
        pos = {nid: (x, -y) for nid, (x, y) in layered_positions(nodes).items()}
    else:
        g = nx.DiGraph()
        for n in nodes:
            g.add_node(n["id"])
        for e in edges:
            if e["source"] in keep and e["target"] in keep:
                g.add_edge(e["source"], e["target"])
        pos = nx.spring_layout(g, seed=42, k=0.7)

    edge_x, edge_y = [], []
    for e in edges:
        if e["source"] in pos and e["target"] in pos:
            x0, y0 = pos[e["source"]]
            x1, y1 = pos[e["target"]]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.8, color="#bbb"), hoverinfo="none",
    )

    node_x, node_y, colors, texts, sizes, line_widths = [], [], [], [], [], []
    for n in nodes:
        if n["id"] not in pos:
            continue
        x, y = pos[n["id"]]
        node_x.append(x)
        node_y.append(y)
        colors.append(_color(n))
        texts.append(f"{n['label']} ({n['type']}, {n.get('observability')})")
        sizes.append(22 if n["id"] in highlight else 14)
        line_widths.append(3 if n["id"] in highlight else 1)
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers", hoverinfo="text",
        text=texts,
        marker=dict(size=sizes, color=colors, line=dict(width=line_widths, color="#333")),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False, hovermode="closest",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=650,
    )
    return fig
