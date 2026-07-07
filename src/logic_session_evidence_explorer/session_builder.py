"""Assemble a complete :class:`SessionEvidence` from raw inputs.

This is the orchestration layer used by both the Streamlit app and the CLI. It:

1. links each non-reference audio file to an inferred track,
2. optionally attaches descriptors, MIDI, MusicXML and channel-strip notes,
3. generates hidden-state markers for Logic-native state exports cannot reveal,
4. runs the recommendation engine.

The hidden-state markers are central to the research framing: they are emitted
deliberately and unconditionally, because the point is to make what we *cannot*
observe as visible as what we can.
"""

from __future__ import annotations

import os
from typing import Optional

from . import audio_descriptors, observation_model, recommendations, utils
from .matching import names_match
from .models import (
    HiddenStateMarker,
    InferredTrackState,
    SessionEvidence,
)


def _hidden_marker(target_id: str, hstype: str, definition: dict) -> HiddenStateMarker:
    return HiddenStateMarker(
        id=utils.make_id("hidden"),
        target_id=target_id,
        hidden_state_type=hstype,
        description=definition["description"],
        consequence=definition["consequence"],
        possible_sources=list(observation_model.POSSIBLE_SOURCES),
    )


def build_inferred_tracks(session: SessionEvidence) -> list[InferredTrackState]:
    """Create one inferred track per non-mixdown, non-reference stem."""

    # MIDI track names / score part names link to inferred tracks through the
    # same shared token matcher the graph builder uses for its linked_to_midi /
    # linked_to_score_part edges, so the model and the graph agree.
    midi_names = session.midi_evidence.track_names if session.midi_evidence else []
    part_names = session.musicxml_evidence.part_names if session.musicxml_evidence else []

    tracks: list[InferredTrackState] = []
    for audio in session.audio_files:
        if audio.is_mixdown or audio.is_reference:
            continue
        observed = ["file_name"]
        if audio.duration_seconds is not None:
            observed.append("duration_seconds")
        if audio.sample_rate is not None:
            observed.append("sample_rate")

        note_ids = [
            n.id
            for n in session.channel_strip_notes
            if names_match(n.track_name, audio.inferred_track_name or audio.file_name)
        ]

        # Fields the user has annotated move from "hidden" to "annotated";
        # both sets are derived from the declarative observation model.
        # Collect across notes, then order by the model's field order so the
        # exported list is stable regardless of note order.
        asserted: set[str] = set()
        for note in session.channel_strip_notes:
            if note.id in note_ids:
                asserted.update(observation_model.annotated_fields_from_note(note))
        annotated_fields = [
            f for f in observation_model.NOTE_FIELD_ASSERTIONS.values() if f in asserted
        ]
        hidden_fields = observation_model.hidden_fields_for_track(annotated_fields)

        track_name = audio.inferred_track_name or audio.file_name
        track = InferredTrackState(
            id=utils.make_id("track"),
            name=track_name,
            role=audio.inferred_role,
            source_audio_id=audio.id,
            linked_midi_track_names=[n for n in midi_names if names_match(n, track_name)],
            linked_musicxml_parts=[p for p in part_names if names_match(p, track_name)],
            channel_strip_note_ids=note_ids,
            descriptor_id=audio.descriptor_id,
            confidence=audio.confidence,
            observed_fields=observed,
            inferred_fields=["role", "track_name"] + annotated_fields,
            hidden_fields=hidden_fields,
        )
        tracks.append(track)
    return tracks


def generate_hidden_state_markers(session: SessionEvidence) -> list[HiddenStateMarker]:
    """Derive hidden-state markers from the declarative observation model.

    Session-level definitions always emit one marker; track-level definitions
    emit one marker per inferred track whose corresponding field has not been
    lifted by a user annotation. Deriving (rather than hard-coding) makes the
    marker set checkable for completeness against the model.
    """

    markers: list[HiddenStateMarker] = []

    for hstype, definition in observation_model.session_level_definitions():
        markers.append(_hidden_marker("session", hstype, definition))

    for hstype, definition in observation_model.track_level_definitions():
        for track in session.inferred_tracks:
            if definition["field"] in track.hidden_fields:
                markers.append(_hidden_marker(track.id, hstype, definition))
    return markers


def attach_descriptors(session: SessionEvidence, *, estimate_tempo: bool = True) -> None:
    """Extract descriptors for every audio file / reference that has a path."""

    for audio in session.audio_files:
        if not audio.file_path or not os.path.exists(audio.file_path):
            continue
        desc = audio_descriptors.extract_descriptors(
            audio.file_path,
            source_id=audio.id,
            file_name=audio.file_name,
            estimate_tempo=estimate_tempo,
        )
        audio.descriptor_id = desc.id
        if audio.duration_seconds is None:
            audio.duration_seconds = desc.duration_seconds
        if audio.sample_rate is None:
            audio.sample_rate = desc.sample_rate
        session.descriptors.append(desc)

    for ref in session.reference_tracks:
        if not ref.file_path or not os.path.exists(ref.file_path):
            continue
        desc = audio_descriptors.extract_descriptors(
            ref.file_path,
            source_id=ref.id,
            source_type="reference_track",
            file_name=ref.file_name,
            estimate_tempo=estimate_tempo,
        )
        ref.descriptor_id = desc.id
        session.descriptors.append(desc)


def _descriptor_by_id(session: SessionEvidence, descriptor_id):
    for d in session.descriptors:
        if d.id == descriptor_id:
            return d
    return None


def attach_signal_comparisons(session: SessionEvidence) -> None:
    """Run stem-sum reconciliation and reference comparison when the needed
    audio files are on disk. Failures degrade to warnings on the result."""

    from . import signal_comparisons

    def _on_disk(obj):
        return obj.file_path and os.path.exists(obj.file_path)

    mixdown = next((a for a in session.audio_files if a.is_mixdown and _on_disk(a)), None)
    if not mixdown:
        return

    stems = {
        a.id: a.file_path
        for a in session.audio_files
        if not a.is_mixdown and not a.is_reference and _on_disk(a)
    }
    if len(stems) >= 2:
        session.stem_sum_reconciliation = signal_comparisons.reconcile_stem_sum(
            stems, mixdown.file_path, mixdown_audio_id=mixdown.id
        )

    references = [a for a in session.audio_files if a.is_reference and _on_disk(a)]
    # A dedicated reference that duplicates a file already in the stem pool
    # (same file uploaded to both uploaders) must be compared only once —
    # mirroring the graph's node dedup.
    audio_file_names = {a.file_name for a in session.audio_files}
    references += [
        r for r in session.reference_tracks
        if _on_disk(r) and r.file_name not in audio_file_names
    ]
    for ref in references:
        session.reference_comparisons.append(
            signal_comparisons.compare_to_reference(
                mixdown.file_path,
                ref.file_path,
                mixdown_audio_id=mixdown.id,
                reference_id=ref.id,
                mixdown_descriptor=_descriptor_by_id(session, mixdown.descriptor_id),
                reference_descriptor=_descriptor_by_id(session, ref.descriptor_id),
            )
        )


def finalize_session(session: SessionEvidence, *, with_descriptors: bool = True) -> SessionEvidence:
    """Run the full assembly pipeline on a session that already has audio_files
    (and optionally MIDI / MusicXML / notes) populated."""

    if with_descriptors:
        attach_descriptors(session)
        attach_signal_comparisons(session)
    session.inferred_tracks = build_inferred_tracks(session)
    # Re-point inferred track descriptor ids now that descriptors exist.
    for track in session.inferred_tracks:
        for audio in session.audio_files:
            if audio.id == track.source_audio_id and audio.descriptor_id:
                track.descriptor_id = audio.descriptor_id
    session.hidden_state_markers = generate_hidden_state_markers(session)
    session.recommendations = recommendations.generate_recommendations(session)
    return session
