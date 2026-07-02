"""Graph visualisation helpers (PyVis primary, Plotly fallback).

The visualisation colour-codes nodes by *observability* so that observed
evidence, inferred state, user annotations and hidden-state markers are
visually distinct — the core interpretability affordance of the tool.
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
    ("Descriptor", "derived"),
    ("Hidden state", "hidden"),
    ("Recommendation", "derived"),
]


def _color(node: dict) -> str:
    return OBSERVABILITY_COLORS.get(node.get("observability", "unknown"), "#7F8C8D")


def filter_graph(export, *, show_descriptors=True, show_hidden=True, show_recommendations=True,
                 show_score=True, observability_only=None):
    """Return (nodes, edges) after applying UI filters.

    ``observability_only`` restricts to a single observability class when set
    (e.g. ``"observed"`` / ``"inferred"`` / ``"hidden"``).
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


def build_pyvis_html(session: SessionEvidence, *, height: str = "650px", **filters) -> str:
    """Render the session graph to standalone PyVis HTML. Raises if PyVis is absent."""

    from pyvis.network import Network

    export = build_graph_export(session)
    nodes, edges = filter_graph(export, **filters)

    net = Network(height=height, width="100%", directed=True, bgcolor="#ffffff", font_color="#222")
    net.barnes_hut(gravity=-8000, spring_length=120)
    for n in nodes:
        title_bits = [f"type: {n['type']}", f"observability: {n.get('observability')}"]
        if n.get("role"):
            title_bits.append(f"role: {n['role']}")
        if n.get("confidence") is not None:
            title_bits.append(f"confidence: {n['confidence']}")
        if n.get("description"):
            title_bits.append(n["description"])
        net.add_node(
            n["id"],
            label=n["label"],
            color=_color(n),
            shape=TYPE_SHAPES.get(n["type"], "dot"),
            title="\n".join(title_bits),
        )
    for e in edges:
        net.add_edge(e["source"], e["target"], title=e["type"], arrows="to")

    try:
        return net.generate_html(notebook=False)
    except TypeError:  # older pyvis
        return net.generate_html()


def build_plotly_figure(session: SessionEvidence, **filters):
    """Render the session graph as a Plotly figure (fallback backend)."""

    import networkx as nx
    import plotly.graph_objects as go

    export = build_graph_export(session)
    nodes, edges = filter_graph(export, **filters)
    keep = {n["id"] for n in nodes}

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

    node_x, node_y, colors, texts = [], [], [], []
    for n in nodes:
        if n["id"] not in pos:
            continue
        x, y = pos[n["id"]]
        node_x.append(x)
        node_y.append(y)
        colors.append(_color(n))
        texts.append(f"{n['label']} ({n['type']}, {n.get('observability')})")
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers", hoverinfo="text",
        text=texts, marker=dict(size=14, color=colors, line=dict(width=1, color="#333")),
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
