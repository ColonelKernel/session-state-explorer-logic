"""Versioned, DAW-agnostic canonical session-state schema (v0.2.0).

This is the shared representation the cross-DAW program normalizes into. It is
deliberately **not** designed around any single DAW: it must represent Logic,
Ableton and REAPER snapshots and extend to Cubase, while preserving each
platform's native concepts under ``extensions.<daw>`` and keeping uncertainty
and provenance first-class.

Design choices (pragmatic, per the program plan):

- One wide :class:`CanonicalEntity` with a ``kind`` discriminator, an
  ``attributes`` bag for kind-specific scalars, and a ``refs`` map for typed
  relationships. This serialises cleanly through homogeneous ``list`` fields
  (a subclass-per-kind design would silently drop subclass fields when a
  pydantic ``list[Base]`` is dumped).
- Every entity carries an ``evidence`` class (observed / inferred / annotated /
  hidden), an ``availability`` status, and an optional :class:`Provenance` —
  with a ``field_provenance`` map for per-field overrides, so provenance is
  inspectable without bloating every scalar.
- The canonical **core is smaller** than the union of DAW features; native
  concepts live in ``extensions`` (namespaced), never forced into the core.

Reuses the pydantic-or-dataclass fallback from :mod:`..models`.
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import BaseModel, Field, to_dict  # noqa: F401 (re-exported)

CANONICAL_SCHEMA_VERSION = "0.2.0"

# --------------------------------------------------------------------------- #
# Controlled vocabularies (directive PART 12-15)
# --------------------------------------------------------------------------- #
EVIDENCE_LEVELS = {"observed", "inferred", "annotated", "hidden", "derived"}

AVAILABILITY = {
    "available", "not_present", "inaccessible", "unsupported",
    "not_applicable", "parse_error", "redacted", "unknown",
}

SOURCE_STABILITY = {
    "official_documented", "official_export", "supported_integration",
    "community_documented", "reverse_engineered", "ui_automation",
    "heuristic", "manual",
}

CAPTURE_MODES = {
    "offline_project", "live_session", "exported_interchange",
    "control_surface", "ui_assisted", "hybrid", "manual_annotation",
}

ENTITY_KINDS = {
    "project", "track", "channel", "region", "media_asset", "device",
    "parameter", "send", "bus", "route", "group", "container",
    "automation_lane", "marker", "tempo_event", "meter_event", "key_event",
    "note_sequence", "take", "scene", "launcher_cell", "spatial_entity",
    "annotation", "hidden_state",
}

# Shared, cross-DAW edge types; native ones are namespaced in edge.extensions.
GRAPH_EDGE_TYPES = {
    "contains", "owns", "uses_channel", "routes_to", "sends_to",
    "receives_from", "processes", "precedes", "follows", "automates",
    "controls", "references_asset", "belongs_to", "member_of",
    "grouped_with", "derived_from", "alternative_of", "sidechain_from",
    "has_hidden_state", "supports_recommendation",
}


# --------------------------------------------------------------------------- #
# Provenance (directive PART 14)
# --------------------------------------------------------------------------- #
class Provenance(BaseModel):
    """How a value was obtained. Evidence, availability and source-stability are
    orthogonal: a value can be ``observed`` yet acquired via fragile
    ``ui_automation`` (directive PART 15)."""

    evidence: str = "observed"
    availability: str = "available"
    capture_method: Optional[str] = None       # one of CAPTURE_MODES
    source_type: Optional[str] = None
    source_reference: Optional[str] = None
    source_stability: Optional[str] = None      # one of SOURCE_STABILITY
    confidence: Optional[float] = None
    inference_method: Optional[str] = None
    inputs: list[str] = Field(default_factory=list)
    author: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Entity
# --------------------------------------------------------------------------- #
class CanonicalEntity(BaseModel):
    """A single canonical session entity.

    ``refs`` maps a relationship role to another entity id (e.g.
    ``{"channel": "ch_1", "parent": "tr_0"}``); the authoritative relationship
    graph is :class:`CanonicalGraph`, but ``refs`` gives direct navigation.
    ``attributes`` holds kind-specific scalars (start, duration, volume,
    category, value, unit, semantic_role, bypassed, mode, bpm, position,
    observability_level, …). ``extensions`` holds namespaced native data.
    """

    id: str
    kind: str
    name: Optional[str] = None
    evidence: str = "observed"
    availability: str = "available"
    provenance: Optional[Provenance] = None
    field_provenance: dict[str, Provenance] = Field(default_factory=dict)
    refs: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
class CanonicalNode(BaseModel):
    id: str
    label: str
    type: str
    evidence: str = "observed"
    availability: str = "available"
    attributes: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


class CanonicalEdge(BaseModel):
    source: str
    target: str
    type: str
    confidence: Optional[float] = None
    extensions: dict[str, Any] = Field(default_factory=dict)


class CanonicalGraph(BaseModel):
    nodes: list[CanonicalNode] = Field(default_factory=list)
    edges: list[CanonicalEdge] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Entities container
# --------------------------------------------------------------------------- #
class Entities(BaseModel):
    tracks: list[CanonicalEntity] = Field(default_factory=list)
    channels: list[CanonicalEntity] = Field(default_factory=list)
    regions: list[CanonicalEntity] = Field(default_factory=list)
    media_assets: list[CanonicalEntity] = Field(default_factory=list)
    devices: list[CanonicalEntity] = Field(default_factory=list)
    parameters: list[CanonicalEntity] = Field(default_factory=list)
    sends: list[CanonicalEntity] = Field(default_factory=list)
    buses: list[CanonicalEntity] = Field(default_factory=list)
    routes: list[CanonicalEntity] = Field(default_factory=list)
    groups: list[CanonicalEntity] = Field(default_factory=list)
    containers: list[CanonicalEntity] = Field(default_factory=list)
    automation_lanes: list[CanonicalEntity] = Field(default_factory=list)
    markers: list[CanonicalEntity] = Field(default_factory=list)
    tempo_events: list[CanonicalEntity] = Field(default_factory=list)
    meter_events: list[CanonicalEntity] = Field(default_factory=list)
    key_events: list[CanonicalEntity] = Field(default_factory=list)
    note_sequences: list[CanonicalEntity] = Field(default_factory=list)
    takes: list[CanonicalEntity] = Field(default_factory=list)
    scenes: list[CanonicalEntity] = Field(default_factory=list)
    launcher_cells: list[CanonicalEntity] = Field(default_factory=list)
    spatial_entities: list[CanonicalEntity] = Field(default_factory=list)
    annotations: list[CanonicalEntity] = Field(default_factory=list)
    hidden_states: list[CanonicalEntity] = Field(default_factory=list)

    def all(self) -> list[CanonicalEntity]:
        out: list[CanonicalEntity] = []
        for name in ENTITY_LIST_FIELDS:
            out.extend(getattr(self, name))
        return out


ENTITY_LIST_FIELDS = [
    "tracks", "channels", "regions", "media_assets", "devices", "parameters",
    "sends", "buses", "routes", "groups", "containers", "automation_lanes",
    "markers", "tempo_events", "meter_events", "key_events", "note_sequences",
    "takes", "scenes", "launcher_cells", "spatial_entities", "annotations",
    "hidden_states",
]


# --------------------------------------------------------------------------- #
# Source, capabilities
# --------------------------------------------------------------------------- #
class Source(BaseModel):
    daw: str
    daw_version: Optional[str] = None
    adapter: str = ""
    adapter_version: Optional[str] = None
    capture_modes: list[str] = Field(default_factory=list)
    synthetic: bool = False   # True for clearly-labelled mock fixtures


class CapabilityDomain(BaseModel):
    support: str = "unsupported"   # observed | partial | inferred | unsupported | unknown
    coverage: str = "none"         # high | medium | low | none
    capture_method: Optional[str] = None
    evidence: Optional[str] = None
    source_stability: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)
    version_dependence: Optional[str] = None


class CapabilityManifest(BaseModel):
    adapter: str = ""
    domains: dict[str, CapabilityDomain] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Root snapshot
# --------------------------------------------------------------------------- #
class CanonicalDAWSnapshot(BaseModel):
    schema_version: str = CANONICAL_SCHEMA_VERSION
    snapshot_id: str = ""
    source: Source = Field(default_factory=lambda: Source(daw="unknown"))
    project: Optional[CanonicalEntity] = None
    timeline: dict[str, Any] = Field(default_factory=dict)
    entities: Entities = Field(default_factory=Entities)
    graph: CanonicalGraph = Field(default_factory=CanonicalGraph)
    capabilities: Optional[CapabilityManifest] = None
    coverage: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def snapshot_to_dict(snapshot: CanonicalDAWSnapshot) -> dict:
    return to_dict(snapshot)


__all__ = [
    "CANONICAL_SCHEMA_VERSION", "EVIDENCE_LEVELS", "AVAILABILITY",
    "SOURCE_STABILITY", "CAPTURE_MODES", "ENTITY_KINDS", "GRAPH_EDGE_TYPES",
    "ENTITY_LIST_FIELDS", "Provenance", "CanonicalEntity", "CanonicalNode",
    "CanonicalEdge", "CanonicalGraph", "Entities", "Source",
    "CapabilityDomain", "CapabilityManifest", "CanonicalDAWSnapshot",
    "snapshot_to_dict",
]
