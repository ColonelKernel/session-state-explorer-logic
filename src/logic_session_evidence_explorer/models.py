"""Typed data models for the Logic Session Evidence Explorer.

These models describe *evidence* about a Logic Pro session rather than the
session itself. The distinction is deliberate: exported audio, MIDI, MusicXML
and user notes are partial, observable traces of a session whose native state
(plug-in chains, automation, routing) remains hidden. The models therefore
carry explicit ``observed`` / ``inferred`` / ``hidden`` bookkeeping.

Pydantic is used where available; a light dataclass-based fallback keeps the
package importable in minimal environments (e.g. running the unit tests
without the full UI stack installed).
"""

from __future__ import annotations

from typing import Any, Optional

try:  # pragma: no cover - exercised implicitly by import
    from pydantic import BaseModel, Field

    _HAS_PYDANTIC = True
except Exception:  # pragma: no cover - fallback path
    _HAS_PYDANTIC = False

    from dataclasses import dataclass, field

    def Field(default=None, default_factory=None, **_kwargs):  # type: ignore
        if default_factory is not None:
            from dataclasses import field as _dc_field

            return _dc_field(default_factory=default_factory)
        return default

    class _BaseModelMeta(type):
        def __new__(mcls, name, bases, namespace):
            cls = super().__new__(mcls, name, bases, namespace)
            if name != "BaseModel":
                cls = dataclass(cls)  # type: ignore
            return cls

    class BaseModel(metaclass=_BaseModelMeta):  # type: ignore
        """Minimal stand-in for :class:`pydantic.BaseModel`."""

        def model_dump(self) -> dict:
            from dataclasses import asdict

            return asdict(self)

        def dict(self) -> dict:  # pydantic v1 compatibility
            return self.model_dump()


SCHEMA_VERSION = "0.1.0"


class AudioDescriptorSet(BaseModel):
    """Numeric descriptors extracted from a single audio file."""

    id: str
    source_id: str
    source_type: str = "audio_evidence"
    file_name: str = ""
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    rms_mean: Optional[float] = None
    rms_std: Optional[float] = None
    peak_amplitude: Optional[float] = None
    dynamic_range_approx: Optional[float] = None
    spectral_centroid_mean: Optional[float] = None
    spectral_bandwidth_mean: Optional[float] = None
    spectral_rolloff_mean: Optional[float] = None
    zero_crossing_rate_mean: Optional[float] = None
    onset_strength_mean: Optional[float] = None
    estimated_tempo: Optional[float] = None
    integrated_loudness_lufs: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class AudioEvidence(BaseModel):
    """A single exported audio file and what we can infer about it."""

    id: str
    file_name: str
    file_path: Optional[str] = None
    upload_name: Optional[str] = None
    inferred_track_name: Optional[str] = None
    inferred_role: Optional[str] = None
    role_explanation: Optional[str] = None
    is_mixdown: bool = False
    is_reference: bool = False
    track_index: Optional[int] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    descriptor_id: Optional[str] = None
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class MidiEvidence(BaseModel):
    id: str
    file_name: str
    track_count: Optional[int] = None
    note_count: Optional[int] = None
    tempo_estimates: list[float] = Field(default_factory=list)
    time_signatures: list[str] = Field(default_factory=list)
    instrument_names: list[str] = Field(default_factory=list)
    track_names: list[str] = Field(default_factory=list)
    note_range: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class MusicXmlEvidence(BaseModel):
    id: str
    file_name: str
    part_count: Optional[int] = None
    measure_count: Optional[int] = None
    part_names: list[str] = Field(default_factory=list)
    detected_keys: list[str] = Field(default_factory=list)
    detected_time_signatures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ChannelStripNote(BaseModel):
    """A user-provided annotation about a track's channel strip.

    These are *assertions by the user*, not state extracted from Logic. The
    graph and UI must always present them as such.
    """

    id: str
    track_name: str
    role: Optional[str] = None
    plugins: list[str] = Field(default_factory=list)
    sends: list[str] = Field(default_factory=list)
    bus: Optional[str] = None
    notes: Optional[str] = None
    confidence: float = 0.5


class ReferenceTrackEvidence(BaseModel):
    id: str
    file_name: str
    file_path: Optional[str] = None
    descriptor_id: Optional[str] = None
    notes: Optional[str] = None


class InferredTrackState(BaseModel):
    """A track reconstructed from the available evidence.

    ``observed_fields`` / ``inferred_fields`` / ``hidden_fields`` make the
    partial-observability of the reconstruction explicit.
    """

    id: str
    name: str
    role: Optional[str] = None
    source_audio_id: Optional[str] = None
    linked_midi_track_names: list[str] = Field(default_factory=list)
    linked_musicxml_parts: list[str] = Field(default_factory=list)
    channel_strip_note_ids: list[str] = Field(default_factory=list)
    descriptor_id: Optional[str] = None
    confidence: float = 0.0
    observed_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    hidden_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HiddenStateMarker(BaseModel):
    """An explicit record of Logic-native state that exports do not reveal."""

    id: str
    target_id: str
    hidden_state_type: str
    description: str
    consequence: str
    possible_sources: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    id: str
    title: str
    severity: str = "info"  # info | suggestion | warning
    confidence: float = 0.5
    related_node_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    suggested_action: str = ""
    caveat: str = ""


class GraphExport(BaseModel):
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class SessionEvidence(BaseModel):
    schema_version: str = SCHEMA_VERSION
    session_name: str = "Untitled Logic Session Evidence"
    daw_name: str = "Logic Pro"
    daw_version: Optional[str] = None
    source_type: str = "logic_exports"  # logic_exports | synthetic_demo | mixed_evidence
    audio_files: list[AudioEvidence] = Field(default_factory=list)
    midi_evidence: Optional[MidiEvidence] = None
    musicxml_evidence: Optional[MusicXmlEvidence] = None
    channel_strip_notes: list[ChannelStripNote] = Field(default_factory=list)
    reference_tracks: list[ReferenceTrackEvidence] = Field(default_factory=list)
    inferred_tracks: list[InferredTrackState] = Field(default_factory=list)
    hidden_state_markers: list[HiddenStateMarker] = Field(default_factory=list)
    descriptors: list[AudioDescriptorSet] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def to_dict(obj: Any) -> Any:
    """Recursively convert models / containers into JSON-serialisable data."""

    if isinstance(obj, BaseModel):
        return to_dict(obj.model_dump())
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj


__all__ = [
    "SCHEMA_VERSION",
    "AudioDescriptorSet",
    "AudioEvidence",
    "MidiEvidence",
    "MusicXmlEvidence",
    "ChannelStripNote",
    "ReferenceTrackEvidence",
    "InferredTrackState",
    "HiddenStateMarker",
    "Recommendation",
    "GraphExport",
    "SessionEvidence",
    "to_dict",
]
