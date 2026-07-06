"""SessionEvidence → nested ``CanonicalSession`` (and losslessly back).

``to_canonical`` maps this repository's native evidence model into the v0.1
nested canonical form that :func:`canonical_snapshot.from_nested.
flatten_session` turns into the flat v0.2 wire snapshot. The mapping is the
honesty core of the Logic adapter:

- Every inferred track becomes a nested ``Track(kind="inferred")`` whose
  entity-level provenance is *inferred* with the track's calibrated
  confidence. Its ``field_provenance`` splits per field: filename-observed
  facts stay *observed*, heuristic role/name are *inferred*, and fields lifted
  by channel-strip notes are *annotation* — never silently promoted.
- Plug-ins named in channel-strip notes ALSO become ``Processor`` entries on
  the matching track, provenance ``annotation``: they render in the canonical
  processing chain while stating loudly that no chain was ever observed.
  ``family`` comes from the documented Logic stock-plug-in catalogue when the
  name is recognised (recognition adds vocabulary, not trust).
- Hidden-state markers pass through; session-level markers are re-targeted at
  the PROJECT entity the flattener will create, so "automation is hidden"
  lands as an availability record on the project rather than a footnote.
- ``to_native`` re-validates the embedded native payload back into a
  :class:`SessionEvidence`; ``to_native(to_canonical(x)) == x`` is a tested
  property.

All canonical ids are namespaced ``logic:`` so Logic evidence can coexist with
other DAWs' snapshots in one graph; native ids survive untouched inside the
native payload.
"""

from __future__ import annotations

from typing import Optional

from canonical_snapshot import nested
from canonical_snapshot.ids import namespaced

from .. import logic_catalog, observation_model
from ..models import (
    AudioDescriptorSet,
    AudioEvidence,
    ChannelStripNote,
    HiddenStateMarker,
    InferredTrackState,
    Recommendation,
    ReferenceComparison,
    ReferenceTrackEvidence,
    SessionEvidence,
    StemSumReconciliation,
)

# The canonical dialect tag (id namespace) and the SourceInfo.daw identifier
# the exporter uses. flatten_session names its PROJECT entity
# f"{source.daw}:project", so session-level hidden-state markers are
# re-targeted at PROJECT_ENTITY_ID here.
DIALECT = "logic"
DAW_ID = "logic_pro"
PROJECT_ENTITY_ID = f"{DAW_ID}:project"

NATIVE_MODEL_NAME = "SessionEvidence"

# Native evidence field names → nested Track field names. Only track_name
# differs; audio-side observed fields (file_name, duration_seconds,
# sample_rate) keep their names — they describe the source evidence and the
# flattener carries their provenance through verbatim.
_TRACK_FIELD_NAMES = {"track_name": "name"}

# Fields that enter a track only through a channel-strip note assertion.
_NOTE_ASSERTED_FIELDS = frozenset(observation_model.NOTE_FIELD_ASSERTIONS.values())


def _ns(raw_id: str) -> str:
    return namespaced(DIALECT, raw_id)


def _ns_opt(raw_id: Optional[str]) -> Optional[str]:
    return _ns(raw_id) if raw_id else None


# --------------------------------------------------------------------------- #
# Evidence-bundle members: field-compatible with the nested classes, so each
# mapping is a model_dump + id namespacing (+ any documented renames).
# --------------------------------------------------------------------------- #
def _map_audio(audio: AudioEvidence) -> nested.AudioEvidence:
    data = audio.model_dump()
    data["id"] = _ns(data["id"])
    data["descriptor_id"] = _ns_opt(data.get("descriptor_id"))
    return nested.AudioEvidence(**data)


def _map_note(note: ChannelStripNote) -> nested.ChannelStripNote:
    data = note.model_dump()
    data["id"] = _ns(data["id"])
    return nested.ChannelStripNote(**data)


def _map_reference(ref: ReferenceTrackEvidence) -> nested.ReferenceTrackEvidence:
    data = ref.model_dump()
    data["id"] = _ns(data["id"])
    data["descriptor_id"] = _ns_opt(data.get("descriptor_id"))
    return nested.ReferenceTrackEvidence(**data)


def _map_stem_sum(recon: StemSumReconciliation) -> nested.StemSumReconciliation:
    data = recon.model_dump()
    data["id"] = _ns(data["id"])
    data["mixdown_audio_id"] = _ns(data["mixdown_audio_id"])
    data["stem_audio_ids"] = [_ns(i) for i in data["stem_audio_ids"]]
    return nested.StemSumReconciliation(**data)


def _map_reference_comparison(comp: ReferenceComparison) -> nested.ReferenceComparison:
    data = comp.model_dump()
    data["id"] = _ns(data["id"])
    data["mixdown_audio_id"] = _ns(data["mixdown_audio_id"])
    data["reference_id"] = _ns(data["reference_id"])
    return nested.ReferenceComparison(**data)


def _map_descriptor(desc: AudioDescriptorSet) -> nested.AudioDescriptorSet:
    data = desc.model_dump()
    data["id"] = _ns(data["id"])
    data["source_id"] = _ns(data["source_id"])
    # Documented rename: this repo's dynamic_range_approx is the nested
    # contract's dynamic_range_db (same peak-vs-noise-floor approximation).
    data["dynamic_range_db"] = data.pop("dynamic_range_approx")
    # A descriptor set only exists here because extraction ran on real audio.
    data["available"] = True
    return nested.AudioDescriptorSet(**data)


def _map_marker(marker: HiddenStateMarker) -> nested.HiddenStateMarker:
    data = marker.model_dump()
    data["id"] = _ns(data["id"])
    # Session-level markers target the PROJECT entity the flattener creates;
    # track-level markers keep their (namespaced) track target.
    data["target_id"] = (
        PROJECT_ENTITY_ID if data["target_id"] == "session" else _ns(data["target_id"])
    )
    return nested.HiddenStateMarker(**data)


def _map_recommendation(rec: Recommendation) -> nested.Recommendation:
    data = rec.model_dump()
    data["id"] = _ns(data["id"])
    data["related_node_ids"] = [_ns(i) for i in data["related_node_ids"]]
    if not data.get("caveat"):
        # The nested default caveat is better than an empty string.
        data.pop("caveat", None)
    data.setdefault("references", [])
    return nested.Recommendation(**data)


# --------------------------------------------------------------------------- #
# Tracks and their note-asserted processors
# --------------------------------------------------------------------------- #
def _note_processors(
    track: InferredTrackState,
    notes_by_id: dict[str, ChannelStripNote],
) -> list[nested.Processor]:
    """Plug-ins asserted by the track's channel-strip notes, as Processors.

    Provenance is ``annotation`` throughout: these render in the canonical
    processing chain while stating that no chain was ever observed in Logic.
    """

    processors: list[nested.Processor] = []
    index = 0
    for note_id in track.channel_strip_note_ids:
        note = notes_by_id.get(note_id)
        if note is None:
            continue
        for plugin_name in note.plugins:
            info = logic_catalog.lookup_plugin(plugin_name)
            extras = {"note_id": _ns(note.id)}
            if info is not None:
                extras["catalog_name"] = info.name
                extras["catalog_generation"] = info.generation
            processors.append(
                nested.Processor(
                    id=_ns(f"{track.id}:plugin_{index + 1}"),
                    track_id=_ns(track.id),
                    index=index,
                    name=plugin_name,
                    kind="logic_stock" if info is not None else None,
                    family=info.category if info is not None else None,
                    provenance=nested.annotation(
                        explanation=(
                            "Plug-in asserted by a user channel-strip note; identity, "
                            "order and settings were never observed in Logic."
                        ),
                        confidence=note.confidence,
                        source_artifact="channel_strip_note",
                    ),
                    extras=extras,
                )
            )
            index += 1
    return processors


def _track_field_provenance(
    track: InferredTrackState,
    source_audio: Optional[AudioEvidence],
    source_artifact: str,
) -> dict[str, nested.Provenance]:
    observed = nested.Provenance(observability="observed", source_artifact=source_artifact)
    field_provenance: dict[str, nested.Provenance] = {}
    for field in track.observed_fields:
        field_provenance[_TRACK_FIELD_NAMES.get(field, field)] = observed
    for field in track.inferred_fields:
        if field in _NOTE_ASSERTED_FIELDS:
            # Lifted from "hidden" by a user assertion — annotation, never a
            # silent promotion to inference.
            field_provenance[field] = nested.annotation(
                explanation="Asserted by a user channel-strip note, not extracted from Logic.",
                confidence=0.5,
                source_artifact="channel_strip_note",
            )
        else:
            explanation = None
            if field == "role" and source_audio is not None:
                explanation = source_audio.role_explanation
            field_provenance[_TRACK_FIELD_NAMES.get(field, field)] = nested.inferred(
                explanation=explanation,
                confidence=track.confidence,
                source_artifact=source_artifact,
            )
    return field_provenance


def _map_track(
    track: InferredTrackState,
    index: int,
    audio_by_id: dict[str, AudioEvidence],
    notes_by_id: dict[str, ChannelStripNote],
    source_artifact: str,
) -> nested.Track:
    source_audio = audio_by_id.get(track.source_audio_id or "")
    extras = {
        "source_audio_id": _ns_opt(track.source_audio_id),
        "linked_midi_track_names": list(track.linked_midi_track_names),
        "linked_musicxml_parts": list(track.linked_musicxml_parts),
        "channel_strip_note_ids": [_ns(i) for i in track.channel_strip_note_ids],
        "descriptor_id": _ns_opt(track.descriptor_id),
        "hidden_fields": list(track.hidden_fields),
        "observed_fields": list(track.observed_fields),
        "inferred_fields": list(track.inferred_fields),
    }
    return nested.Track(
        id=_ns(track.id),
        index=index,
        name=track.name,
        kind="inferred",
        role=track.role,
        processors=_note_processors(track, notes_by_id),
        descriptor_id=_ns_opt(track.descriptor_id),
        confidence=track.confidence,
        provenance=nested.Provenance(
            observability="inferred",
            confidence=track.confidence,
            source_artifact=source_artifact,
            explanation=(
                "Track reconstructed from exported audio evidence; "
                "no Logic project file was read."
            ),
        ),
        field_provenance=_track_field_provenance(track, source_audio, source_artifact),
        extras={k: v for k, v in extras.items() if v is not None},
        warnings=list(track.warnings),
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def to_canonical(
    evidence: SessionEvidence,
    source_artifact: str = "exported_audio",
) -> nested.CanonicalSession:
    """Map a native :class:`SessionEvidence` into the nested canonical form."""

    audio_by_id = {a.id: a for a in evidence.audio_files}
    notes_by_id = {n.id: n for n in evidence.channel_strip_notes}

    bundle = nested.EvidenceBundle(
        audio_files=[_map_audio(a) for a in evidence.audio_files],
        midi_evidence=(
            nested.MidiEvidence(**{**evidence.midi_evidence.model_dump(),
                                   "id": _ns(evidence.midi_evidence.id)})
            if evidence.midi_evidence is not None
            else None
        ),
        musicxml_evidence=(
            nested.MusicXmlEvidence(**{**evidence.musicxml_evidence.model_dump(),
                                       "id": _ns(evidence.musicxml_evidence.id)})
            if evidence.musicxml_evidence is not None
            else None
        ),
        channel_strip_notes=[_map_note(n) for n in evidence.channel_strip_notes],
        reference_tracks=[_map_reference(r) for r in evidence.reference_tracks],
        stem_sum_reconciliation=(
            _map_stem_sum(evidence.stem_sum_reconciliation)
            if evidence.stem_sum_reconciliation is not None
            else None
        ),
        reference_comparisons=[
            _map_reference_comparison(c) for c in evidence.reference_comparisons
        ],
    )

    return nested.CanonicalSession(
        dialect=DIALECT,
        name=evidence.session_name,
        tracks=[
            _map_track(t, i, audio_by_id, notes_by_id, source_artifact)
            for i, t in enumerate(evidence.inferred_tracks)
        ],
        evidence=bundle,
        hidden_state_markers=[_map_marker(m) for m in evidence.hidden_state_markers],
        descriptors=[_map_descriptor(d) for d in evidence.descriptors],
        recommendations=[_map_recommendation(r) for r in evidence.recommendations],
        warnings=list(evidence.warnings),
        metadata={
            "source_artifact": source_artifact,
            "daw_version": evidence.daw_version,
            "source_type": evidence.source_type,
        },
        native=nested.NativePayload(
            dialect=DIALECT,
            model_name=NATIVE_MODEL_NAME,
            model=evidence.model_dump(),
        ),
    )


def to_native(session: nested.CanonicalSession) -> SessionEvidence:
    """Re-validate the embedded native payload back into a SessionEvidence.

    Exact round-trip: ``to_native(to_canonical(x)) == x`` (tested).
    """

    if session.native is None:
        raise ValueError("Canonical session carries no native payload.")
    if session.native.dialect != DIALECT or session.native.model_name != NATIVE_MODEL_NAME:
        raise ValueError(
            f"Native payload is {session.native.dialect}/{session.native.model_name}, "
            f"expected {DIALECT}/{NATIVE_MODEL_NAME}."
        )
    return SessionEvidence.model_validate(session.native.model)
