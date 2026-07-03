"""Build an interpretable session graph from :class:`SessionEvidence`.

Every node carries an ``observability`` tag — ``observed`` (directly present in
an export), ``inferred`` (derived by this tool), ``annotation`` (user-provided),
``hidden`` (Logic-native state we cannot see) or ``derived`` (descriptors /
recommendations). This tag is what lets the UI and the JSON export make the
partial observability of the reconstruction explicit.
"""

from __future__ import annotations

from typing import Any

try:
    import networkx as nx

    _HAS_NX = True
except Exception:  # pragma: no cover - optional at graph-export time
    _HAS_NX = False

from .matching import name_match_confidence, names_match
from .models import GraphExport, SessionEvidence

OBSERVED = "observed"
INFERRED = "inferred"
ANNOTATION = "annotation"
HIDDEN = "hidden"
DERIVED = "derived"


def _add_node(nodes: dict, node_id: str, **attrs) -> None:
    nodes[node_id] = {"id": node_id, **attrs}


def build_graph_export(session: SessionEvidence) -> GraphExport:
    """Construct the node/edge lists (backend-independent)."""

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def edge(source: str, target: str, etype: str, confidence: float | None = None) -> None:
        if source in nodes and target in nodes:
            e: dict[str, Any] = {"source": source, "target": target, "type": etype}
            if confidence is not None:
                e["confidence"] = round(confidence, 3)
            edges.append(e)

    # Session root ---------------------------------------------------------- #
    session_id = "session"
    _add_node(
        nodes,
        session_id,
        label=session.session_name,
        type="session",
        observability=OBSERVED,
    )

    # Audio evidence + mixdown / reference specialisation ------------------- #
    for audio in session.audio_files:
        if audio.is_reference:
            node_type = "reference_track"
        elif audio.is_mixdown:
            node_type = "mixdown"
        else:
            node_type = "audio_evidence"
        _add_node(
            nodes,
            audio.id,
            label=audio.inferred_track_name or audio.file_name,
            type=node_type,
            observability=OBSERVED,
            role=audio.inferred_role,
            confidence=audio.confidence,
            file_name=audio.file_name,
        )
        edge(session_id, audio.id, "contains_audio")

    # Dedicated reference tracks (uploaded separately from the stem pool).
    # Skip any that duplicate a file already present in the stem pool, so the
    # same physical file never appears as two nodes.
    audio_file_names = {a.file_name for a in session.audio_files}
    for ref in session.reference_tracks:
        if ref.file_name in audio_file_names:
            continue
        _add_node(
            nodes,
            ref.id,
            label=ref.file_name,
            type="reference_track",
            observability=OBSERVED,
            file_name=ref.file_name,
        )
        edge(session_id, ref.id, "contains_audio")

    # Descriptors. Only added when their source node exists, so a descriptor
    # can never appear as an orphan in the graph. ---------------------------- #
    for desc in session.descriptors:
        if desc.source_id not in nodes:
            continue
        _add_node(
            nodes,
            desc.id,
            label=f"Descriptors: {desc.file_name}",
            type="descriptor_set",
            observability=DERIVED,
        )
        edge(desc.source_id, desc.id, "has_descriptor")

    # Inferred tracks ------------------------------------------------------ #
    for track in session.inferred_tracks:
        _add_node(
            nodes,
            track.id,
            label=track.name,
            type="inferred_track",
            observability=INFERRED,
            role=track.role,
            confidence=track.confidence,
        )
        if track.source_audio_id:
            edge(track.source_audio_id, track.id, "infers_track", track.confidence)
        if track.descriptor_id:
            edge(track.id, track.descriptor_id, "has_descriptor")

    # MIDI ----------------------------------------------------------------- #
    if session.midi_evidence:
        midi = session.midi_evidence
        _add_node(
            nodes,
            midi.id,
            label=f"MIDI: {midi.file_name}",
            type="midi_file",
            observability=OBSERVED,
        )
        edge(session_id, midi.id, "contains_audio")
        for i, name in enumerate(midi.track_names):
            tid = f"{midi.id}_track_{i}"
            _add_node(nodes, tid, label=name, type="midi_track", observability=OBSERVED)
            edge(midi.id, tid, "contains_audio")
            # Link MIDI track to inferred tracks whose name matches.
            for track in session.inferred_tracks:
                if names_match(name, track.name):
                    edge(track.id, tid, "linked_to_midi",
                         name_match_confidence(name, track.name))

    # MusicXML ------------------------------------------------------------- #
    if session.musicxml_evidence:
        mxl = session.musicxml_evidence
        _add_node(
            nodes,
            mxl.id,
            label=f"Score: {mxl.file_name}",
            type="musicxml_file",
            observability=OBSERVED,
        )
        edge(session_id, mxl.id, "contains_audio")
        for i, name in enumerate(mxl.part_names):
            pid = f"{mxl.id}_part_{i}"
            _add_node(nodes, pid, label=name, type="musicxml_part", observability=OBSERVED)
            edge(mxl.id, pid, "contains_audio")
            for track in session.inferred_tracks:
                if names_match(name, track.name):
                    edge(track.id, pid, "linked_to_score_part",
                         name_match_confidence(name, track.name))

    # Channel-strip notes (+ plugin/send/bus sub-nodes) -------------------- #
    for note in session.channel_strip_notes:
        _add_node(
            nodes,
            note.id,
            label=f"Notes: {note.track_name}",
            type="channel_strip_note",
            observability=ANNOTATION,
            confidence=note.confidence,
        )
        # Attach note to matching inferred track, else to session.
        attached = False
        for track in session.inferred_tracks:
            if names_match(note.track_name, track.name):
                edge(track.id, note.id, "annotated_by",
                     name_match_confidence(note.track_name, track.name))
                attached = True
        if not attached:
            edge(session_id, note.id, "annotated_by", note.confidence)

        for j, plugin in enumerate(note.plugins):
            nid = f"{note.id}_plugin_{j}"
            _add_node(nodes, nid, label=plugin, type="plugin_note", observability=ANNOTATION)
            edge(note.id, nid, "mentions_plugin")
        for j, send in enumerate(note.sends):
            nid = f"{note.id}_send_{j}"
            _add_node(nodes, nid, label=send, type="send_note", observability=ANNOTATION)
            edge(note.id, nid, "mentions_send")
        if note.bus:
            nid = f"{note.id}_bus"
            _add_node(nodes, nid, label=note.bus, type="bus_note", observability=ANNOTATION)
            edge(note.id, nid, "mentions_bus")

    # Reference comparison edges (mixdown -> reference) -------------------- #
    mixdowns = [a.id for a in session.audio_files if a.is_mixdown]
    references = [a.id for a in session.audio_files if a.is_reference] + [
        r.id for r in session.reference_tracks
    ]
    for mix in mixdowns:
        for ref in references:
            edge(mix, ref, "compared_to_reference")

    # Hidden-state markers ------------------------------------------------- #
    for marker in session.hidden_state_markers:
        _add_node(
            nodes,
            marker.id,
            label=marker.hidden_state_type,
            type="hidden_state_marker",
            observability=HIDDEN,
            description=marker.description,
        )
        target = marker.target_id if marker.target_id in nodes else session_id
        edge(target, marker.id, "has_hidden_state")

    # Recommendations ------------------------------------------------------ #
    for rec in session.recommendations:
        _add_node(
            nodes,
            rec.id,
            label=rec.title,
            type="recommendation",
            observability=DERIVED,
            severity=rec.severity,
            confidence=rec.confidence,
        )
        linked = [nid for nid in rec.related_node_ids if nid in nodes] or [session_id]
        for nid in linked:
            edge(nid, rec.id, "supports_recommendation", rec.confidence)

    node_list = list(nodes.values())
    counts = _observability_counts(node_list)
    metadata = {
        "num_audio_files": len(session.audio_files),
        "num_inferred_tracks": len(session.inferred_tracks),
        "num_descriptors": len(session.descriptors),
        "num_annotations": len(session.channel_strip_notes),
        "num_hidden_state_markers": len(session.hidden_state_markers),
        "num_recommendations": len(session.recommendations),
        "num_nodes": len(node_list),
        "num_edges": len(edges),
        "observability_counts": counts,
        "observability_percentages": _percentages(counts),
    }
    return GraphExport(nodes=node_list, edges=edges, metadata=metadata)


def _observability_counts(nodes: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        key = node.get("observability", "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _percentages(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values()) or 1
    return {k: round(100.0 * v / total, 1) for k, v in counts.items()}


def build_networkx_graph(session: SessionEvidence):
    """Return a populated :class:`networkx.DiGraph` (requires networkx)."""

    if not _HAS_NX:  # pragma: no cover - optional dependency
        raise RuntimeError("networkx is not installed; use build_graph_export instead.")

    export = build_graph_export(session)
    graph = nx.DiGraph()
    graph.graph.update(export.metadata)
    for node in export.nodes:
        graph.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
    for e in export.edges:
        graph.add_edge(e["source"], e["target"], **{k: v for k, v in e.items() if k not in ("source", "target")})
    return graph
