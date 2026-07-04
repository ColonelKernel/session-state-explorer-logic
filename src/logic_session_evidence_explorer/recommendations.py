"""Rule-based, explainable recommendation engine.

Each rule inspects the assembled :class:`SessionEvidence` and, when it fires,
returns a :class:`Recommendation` carrying a confidence, the related graph
nodes, an explanation, a suggested action and a caveat. The language is
deliberately human-centered: recommendations describe documentation and
interpretability opportunities, never "the correct mix".
"""

from __future__ import annotations

import math
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
    """Compare silence-gated (active) stem levels in dB.

    Whole-file RMS on Logic's full-song-length exports measures how *often* a
    part plays, not how loud it is; gating on active frames measures level.
    """

    stems = [a for a in session.audio_files if not a.is_mixdown and not a.is_reference]
    values = []
    for a in stems:
        d = _descriptor_for(session, a.id)
        level = (d.active_rms_mean if d and d.active_rms_mean else None) or (
            d.rms_mean if d else None
        )
        if level and level > 0:
            values.append((a, 20.0 * math.log10(level)))
    if len(values) < 3:
        return []
    median_db = statistics.median(v for _a, v in values)
    outliers = [a for a, v in values if v > median_db + 6.0]
    if outliers:
        return [
            Recommendation(
                id=utils.make_id("rec"),
                title="Potential stem-level imbalance detected.",
                severity="warning",
                confidence=0.55,
                related_node_ids=[a.id for a in outliers],
                explanation=(
                    "One or more exported stems sit more than 6 dB above the "
                    "session median, measured on silence-gated (active) RMS so "
                    "sparse parts are compared fairly. This may be intentional, "
                    "printed processing, or an export-level mismatch."
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
        if d is None:
            continue
        # Prefer the silence-gated crest figure; whole-file crest is inflated
        # by silent stretches on sparse stems.
        crest = d.dynamic_range_active_db
        if crest is None:
            crest = d.dynamic_range_approx
        if crest is not None and crest < 6.0:
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


def rule_stem_sum_mismatch(session: SessionEvidence) -> list[Recommendation]:
    recon = session.stem_sum_reconciliation
    if not recon or recon.residual_db is None or recon.residual_db <= -20.0:
        return []
    worst_bands = sorted(
        recon.band_residuals_db.items(), key=lambda kv: kv[1], reverse=True
    )[:3]
    band_text = (
        "; the residual is largest in " + ", ".join(k for k, _v in worst_bands)
        if worst_bands else ""
    )
    return [
        Recommendation(
            id=utils.make_id("rec"),
            title="Mixdown contains processing not present in the stem sum.",
            severity="info",
            confidence=0.6,
            related_node_ids=[recon.mixdown_audio_id, recon.id] + list(recon.stem_audio_ids),
            explanation=(
                f"Summing the exported stems and fitting a single gain leaves a "
                f"residual of {recon.residual_db} dB relative to the mixdown"
                f"{band_text}. This is signal evidence that bus or master "
                "processing, automation, or additional content separates the "
                "stem exports from the final mix."
            ),
            suggested_action=(
                "Document any bus/master processing, or re-export full-length, "
                "bar-1-aligned stems if the mismatch is unexpected."
            ),
            caveat=(
                "A high residual can also come from missing stems or "
                "misaligned exports; it identifies a gap, not its cause."
            ),
        )
    ]


def rule_reference_balance(session: SessionEvidence) -> list[Recommendation]:
    recommendations = []
    for cmp_result in session.reference_comparisons:
        notable = {
            k: v for k, v in cmp_result.band_deltas_db.items() if abs(v) >= 6.0
        }
        if not notable:
            continue
        top = sorted(notable.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        described = ", ".join(
            f"{band}: {delta:+.1f} dB relative to the reference" for band, delta in top
        )
        recommendations.append(
            Recommendation(
                id=utils.make_id("rec"),
                title="Mixdown and reference differ noticeably in spectral balance.",
                severity="info",
                confidence=0.55,
                related_node_ids=[
                    cmp_result.mixdown_audio_id, cmp_result.reference_id, cmp_result.id,
                ],
                explanation=(
                    "Comparing per-band energy fractions (level-independent), the "
                    f"largest differences are {described}."
                ),
                suggested_action=(
                    "Listen to the named bands against the reference and note "
                    "whether the difference is intentional character or worth "
                    "revisiting."
                ),
                caveat=(
                    "A reference is a point of comparison, not an objective "
                    "target; genre and arrangement legitimately move spectral "
                    "balance."
                ),
            )
        )
    return recommendations


RULES: list[Rule] = [
    rule_missing_channel_strip_notes,
    rule_vocal_without_notes,
    rule_mixdown_without_reference,
    rule_stem_level_imbalance,
    rule_printed_processing_ambiguity,
    rule_midi_score_mismatch,
    rule_hidden_routing,
    rule_stem_sum_mismatch,
    rule_reference_balance,
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
