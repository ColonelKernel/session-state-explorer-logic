"""Rule-based, explainable recommendation engine.

Each rule inspects the assembled :class:`SessionEvidence` and, when it fires,
returns a :class:`Recommendation` carrying a confidence, the related graph
nodes, an explanation, a suggested action and a caveat. The language is
deliberately human-centered: recommendations describe documentation and
interpretability opportunities, never "the correct mix".
"""

from __future__ import annotations

import statistics
from typing import Callable

from . import utils
from .matching import names_match
from .models import Recommendation, SessionEvidence

Rule = Callable[[SessionEvidence], list[Recommendation]]


def _descriptor_for(session: SessionEvidence, audio_id: str):
    for track in session.inferred_tracks:
        if track.source_audio_id == audio_id and track.descriptor_id:
            for d in session.descriptors:
                if d.id == track.descriptor_id:
                    return d
    for d in session.descriptors:
        if d.source_id == audio_id:
            return d
    return None


def _has_any_notes(session: SessionEvidence) -> bool:
    return len(session.channel_strip_notes) > 0


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
def rule_missing_channel_strip_notes(session: SessionEvidence) -> list[Recommendation]:
    stems = [a for a in session.audio_files if not a.is_mixdown and not a.is_reference]
    if stems and not _has_any_notes(session):
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Add channel-strip notes to improve DAW-state interpretability.",
                severity="suggestion",
                confidence=0.8,
                related_node_ids=[a.id for a in stems],
                explanation=(
                    "The exported stems reveal audio evidence, but not the Logic "
                    "channel-strip state. Adding simple notes about plug-ins, sends, "
                    "and buses would make the graph more useful for explaining "
                    "production decisions."
                ),
                suggested_action=(
                    "Export or manually enter basic channel-strip notes for each "
                    "stem: plug-ins, sends, bus, and production role."
                ),
                caveat=(
                    "This prototype treats notes as user-provided evidence, not "
                    "automatically extracted Logic-native state."
                ),
            )
        ]
    return []


def rule_vocal_without_notes(session: SessionEvidence) -> list[Recommendation]:
    vocal_stems = [a for a in session.audio_files if a.inferred_role == "Vocal"]
    if not vocal_stems:
        return []
    # A vocal stem counts as documented when ANY channel-strip note names it —
    # the same criterion the graph uses for annotated_by edges, so the rule
    # and the graph can never disagree about the same stem.
    undocumented = [a for a in vocal_stems if not _is_documented(session, a)]
    if undocumented:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Vocal processing state is under-documented.",
                severity="suggestion",
                confidence=0.7,
                related_node_ids=[a.id for a in undocumented],
                explanation=(
                    "The graph contains a vocal-like stem, but there is no visible "
                    "evidence of EQ, compression, de-essing, ambience sends, or "
                    "other vocal-chain decisions."
                ),
                suggested_action=(
                    "Add channel-strip notes or screenshots for the vocal chain if "
                    "you want the session graph to represent editable production intent."
                ),
                caveat=(
                    "A vocal-like filename is not proof of a vocal recording, and "
                    "printed processing cannot be recovered from stem audio alone."
                ),
            )
        ]
    return []


def rule_mixdown_without_reference(session: SessionEvidence) -> list[Recommendation]:
    mixdowns = [a for a in session.audio_files if a.is_mixdown]
    has_reference = any(a.is_reference for a in session.audio_files) or bool(
        session.reference_tracks
    )
    if mixdowns and not has_reference:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Reference-aware evaluation could be added.",
                severity="info",
                confidence=0.6,
                related_node_ids=[a.id for a in mixdowns],
                explanation=(
                    "A stereo mixdown is available, but no reference track was "
                    "supplied. A reference could help compare spectral balance, "
                    "dynamics, and production intent without treating one mix as "
                    "objectively correct."
                ),
                suggested_action=(
                    "Upload a reference track and add a short note about what "
                    "qualities it represents."
                ),
                caveat="A reference is a point of comparison, not an objective target.",
            )
        ]
    return []


def rule_stem_level_imbalance(session: SessionEvidence) -> list[Recommendation]:
    stems = [a for a in session.audio_files if not a.is_mixdown and not a.is_reference]
    values = []
    for a in stems:
        d = _descriptor_for(session, a.id)
        if d and d.rms_mean is not None:
            values.append((a, d.rms_mean))
    if len(values) < 3:
        return []
    median = statistics.median(v for _a, v in values)
    if median <= 0:
        return []
    outliers = [a for a, v in values if v > median * 3.0]
    if outliers:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Potential stem-level imbalance detected.",
                severity="warning",
                confidence=0.55,
                related_node_ids=[a.id for a in outliers],
                explanation=(
                    "One or more exported stems have substantially higher RMS level "
                    "than the session median. This may be intentional, printed "
                    "processing, or an export-level mismatch."
                ),
                suggested_action=(
                    "Check whether stems were exported pre-fader, post-fader, "
                    "normalized, or after bus processing."
                ),
                caveat=(
                    "Level differences can be entirely intentional; this is a "
                    "prompt to verify export settings, not a mixing verdict."
                ),
            )
        ]
    return []


def _is_documented(session: SessionEvidence, audio) -> bool:
    name = audio.inferred_track_name or audio.file_name
    return any(
        names_match(n.track_name, name) for n in session.channel_strip_notes
    )


def rule_printed_processing_ambiguity(session: SessionEvidence) -> list[Recommendation]:
    suspects = []
    for a in session.audio_files:
        if a.is_mixdown or a.is_reference or _is_documented(session, a):
            continue
        d = _descriptor_for(session, a.id)
        if d and d.dynamic_range_approx is not None and d.dynamic_range_approx < 6.0:
            suspects.append(a)
    if suspects:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Printed processing may be present but undocumented.",
                severity="info",
                confidence=0.5,
                related_node_ids=[a.id for a in suspects],
                explanation=(
                    "Some stems show descriptor patterns (low approximate dynamic "
                    "range) that may reflect printed compression, saturation, EQ, or "
                    "limiting, but the graph cannot identify the original Logic "
                    "plug-ins or settings."
                ),
                suggested_action=(
                    "Document whether stems were exported dry, post-insert, "
                    "post-fader, or through buses."
                ),
                caveat=(
                    "Descriptor patterns are suggestive only; they cannot confirm "
                    "that any specific processing was applied."
                ),
            )
        ]
    return []


def rule_midi_score_mismatch(session: SessionEvidence) -> list[Recommendation]:
    part_names: list[str] = []
    if session.midi_evidence:
        part_names.extend(session.midi_evidence.track_names)
    if session.musicxml_evidence:
        part_names.extend(session.musicxml_evidence.part_names)
    part_names = [p for p in part_names if p]
    if not part_names:
        return []
    # Match parts against inferred tracks — the same targets the graph draws
    # linked_to_midi / linked_to_score_part edges to — so an orphan part node
    # in the graph and this rule always agree.
    track_names = [t.name for t in session.inferred_tracks]
    unmatched = [
        p for p in part_names
        if not any(names_match(p, s) for s in track_names)
    ]
    if unmatched:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Some musical parts are not linked to audio evidence.",
                severity="suggestion",
                confidence=0.6,
                related_node_ids=[],
                explanation=(
                    "MIDI or score evidence contains parts that do not clearly "
                    f"match an exported stem (e.g. {', '.join(unmatched[:4])}). "
                    "Linking them would improve the relationship between musical "
                    "structure and acoustic outcome."
                ),
                suggested_action=(
                    "Rename stems consistently or add a manifest mapping score/MIDI "
                    "parts to exported audio files."
                ),
                caveat="Name matching is heuristic and may miss valid pairings.",
            )
        ]
    return []


def rule_hidden_routing(session: SessionEvidence) -> list[Recommendation]:
    stems = [a for a in session.audio_files if not a.is_mixdown and not a.is_reference]
    has_bus_info = any(n.bus or n.sends for n in session.channel_strip_notes)
    if len(stems) >= 4 and not has_bus_info:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Routing graph is probably incomplete.",
                severity="warning",
                confidence=0.65,
                related_node_ids=[a.id for a in stems],
                explanation=(
                    "The session contains multiple stems, but no bus, send, or "
                    "track-stack information. The graph therefore represents a "
                    "flattened export rather than the full Logic mix structure."
                ),
                suggested_action=(
                    "Add bus/send notes or export grouped stems such as drums, "
                    "vocals, guitars, and effects returns."
                ),
                caveat=(
                    "Routing cannot be reliably recovered from stem audio alone; "
                    "this is a documentation prompt."
                ),
            )
        ]
    return []


RULES: list[Rule] = [
    rule_missing_channel_strip_notes,
    rule_vocal_without_notes,
    rule_mixdown_without_reference,
    rule_stem_level_imbalance,
    rule_printed_processing_ambiguity,
    rule_midi_score_mismatch,
    rule_hidden_routing,
]


def generate_recommendations(session: SessionEvidence) -> list[Recommendation]:
    """Run every rule and collect the recommendations that fire."""

    recommendations: list[Recommendation] = []
    for rule in RULES:
        try:
            recommendations.extend(rule(session))
        except Exception as exc:  # pragma: no cover - defensive
            session.warnings.append(f"Recommendation rule '{rule.__name__}' failed: {exc}")
    return recommendations
