"""JSON export helpers for the assembled session.

The bundle format makes observed, inferred, annotated and hidden information
explicit, and records that no native project file was parsed.
"""

from __future__ import annotations

from . import graph_builder
from .models import SCHEMA_VERSION, SessionEvidence, to_dict


def session_evidence_json(session: SessionEvidence) -> dict:
    return to_dict(session)


def graph_json(session: SessionEvidence) -> dict:
    export = graph_builder.build_graph_export(session)
    return {"nodes": export.nodes, "edges": export.edges, "metadata": export.metadata}


def descriptors_json(session: SessionEvidence) -> list:
    return to_dict(session.descriptors)


def recommendations_json(session: SessionEvidence) -> list:
    return to_dict(session.recommendations)


def hidden_state_json(session: SessionEvidence) -> list:
    return to_dict(session.hidden_state_markers)


def full_bundle(session: SessionEvidence) -> dict:
    """Assemble the complete research bundle described in the spec."""

    graph = graph_builder.build_graph_export(session)
    return {
        "schema_version": SCHEMA_VERSION,
        "session_evidence": to_dict(session),
        "graph": {
            "nodes": graph.nodes,
            "edges": graph.edges,
            "metadata": graph.metadata,
        },
        "descriptors": to_dict(session.descriptors),
        "hidden_state_markers": to_dict(session.hidden_state_markers),
        "recommendations": to_dict(session.recommendations),
        "warnings": list(session.warnings),
        "export_metadata": {
            "daw": session.daw_name,
            "mode": "evidence_based",
            "native_project_parsed": False,
        },
    }
