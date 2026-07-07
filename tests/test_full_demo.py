"""Tests for the "Logic Full Evidence Demo" — the full-pipeline showcase.

The full demo synthesizes every evidence kind the pipeline accepts (stems, an
exact-scaled-sum mixdown, a reference track, MIDI, MusicXML, channel-strip
notes) and runs the real assembly pipeline over it, descriptors on. Everything
is generated locally with the stdlib — no network is ever touched.

Signal-dependent tests require librosa (descriptors + signal comparisons) and
mido (MIDI track-name parsing); the module skips without them, matching the
repo's guarded-optional-dependency policy. Canonical-export assertions
additionally skip without the optional ``canonical-snapshot`` package.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("librosa")  # descriptors + stem-sum / reference comparisons
pytest.importorskip("mido")  # MIDI track names feed the evidence-linking tests

from logic_session_evidence_explorer import cli, demo  # noqa: E402
from logic_session_evidence_explorer.models import SessionEvidence  # noqa: E402


@pytest.fixture(scope="module")
def full_session(tmp_path_factory) -> SessionEvidence:
    target = tmp_path_factory.mktemp("full_demo_assets")
    return demo.build_full_demo(target_dir=str(target))


@pytest.fixture(scope="module")
def full_bundle(tmp_path_factory, full_session):
    pytest.importorskip("canonical_snapshot")
    from logic_session_evidence_explorer.canonical_export import (
        export_session_bundle,
        exporter,
    )

    out_dir = tmp_path_factory.mktemp("full_bundle")
    result = export_session_bundle(full_session, str(out_dir))
    files = {
        name: json.load(open(os.path.join(str(out_dir), name), encoding="utf-8"))
        for name in exporter.BUNDLE_FILES
    }
    return {"result": result, "files": files, "out_dir": str(out_dir)}


# --------------------------------------------------------------------------- #
# Generation + scan
# --------------------------------------------------------------------------- #
def test_generates_every_evidence_file(full_session):
    folder = full_session.metadata["audio_dir"]
    expected = [name for name, _k, _f, _a in demo.FULL_DEMO_STEMS] + [
        demo.FULL_DEMO_MIXDOWN_NAME,
        demo.FULL_DEMO_REFERENCE_NAME,
        demo.FULL_DEMO_MIDI_NAME,
        demo.FULL_DEMO_MUSICXML_NAME,
        demo.FULL_DEMO_NOTES_NAME,
        demo.FULL_DEMO_MANIFEST_NAME,
    ]
    for name in expected:
        assert os.path.exists(os.path.join(folder, name)), name


def test_scan_classifies_stems_mixdown_and_reference(full_session):
    assert len(full_session.audio_files) == 10
    mixdowns = [a for a in full_session.audio_files if a.is_mixdown]
    references = [a for a in full_session.audio_files if a.is_reference]
    assert [m.file_name for m in mixdowns] == [demo.FULL_DEMO_MIXDOWN_NAME]
    assert [r.file_name for r in references] == [demo.FULL_DEMO_REFERENCE_NAME]
    # One inferred track per stem; mixdown and reference excluded.
    assert len(full_session.inferred_tracks) == 8
    roles = {t.role for t in full_session.inferred_tracks}
    assert {"Vocal", "Drums", "Bass", "Keys", "Strings", "FX"} <= roles


# --------------------------------------------------------------------------- #
# MIDI + MusicXML evidence and track linking
# --------------------------------------------------------------------------- #
def test_midi_evidence_parsed(full_session):
    midi = full_session.midi_evidence
    assert midi is not None
    for name in demo.FULL_DEMO_MIDI_TRACKS:
        assert name in midi.track_names
    assert midi.note_count and midi.note_count > 0
    assert midi.tempo_estimates == [120.0]
    assert midi.time_signatures == ["4/4"]
    assert midi.note_range  # lowest–highest present


def test_musicxml_evidence_parsed(full_session):
    xml = full_session.musicxml_evidence
    assert xml is not None
    assert xml.part_names == demo.FULL_DEMO_MUSICXML_PARTS
    assert xml.part_count == 3
    assert xml.measure_count == 6
    assert xml.detected_time_signatures == ["4/4"]


def test_tracks_link_to_midi_and_score_parts(full_session):
    by_name = {t.name: t for t in full_session.inferred_tracks}
    assert by_name["Bass DI"].linked_midi_track_names == ["Bass DI"]
    assert by_name["Piano"].linked_midi_track_names == ["Piano"]
    assert by_name["Violins Section"].linked_musicxml_parts == ["Violins Section"]
    # The vocal stem links to the "Lead Vocal" score part despite the Logic
    # "_bip" bounce decoration on the filename.
    assert by_name["Lead Vocal bip"].linked_musicxml_parts == ["Lead Vocal"]
    assert any(t.linked_midi_track_names for t in full_session.inferred_tracks)


# --------------------------------------------------------------------------- #
# Signal comparisons: the satisfying, correct result by construction
# --------------------------------------------------------------------------- #
def test_stem_sum_reconciliation_recovers_the_known_gain(full_session):
    recon = full_session.stem_sum_reconciliation
    assert recon is not None
    assert len(recon.stem_audio_ids) == 8
    # The mixdown is written as the exact scaled sum, so the residual sits at
    # the 16-bit quantisation floor and the fitted gain is the known scale.
    assert recon.residual_db is not None and recon.residual_db < -40.0
    assert recon.fitted_gain == pytest.approx(demo.FULL_DEMO_MIX_GAIN, abs=1e-3)
    assert recon.correlation is not None and recon.correlation > 0.999
    assert "closely" in recon.interpretation


def test_reference_comparison_present_and_descriptive(full_session):
    (comparison,) = full_session.reference_comparisons
    reference = next(a for a in full_session.audio_files if a.is_reference)
    assert comparison.reference_id == reference.id
    assert comparison.band_deltas_db  # per-band spectral deltas computed
    assert comparison.summary


def test_descriptors_extracted_for_every_file_with_distinct_levels(full_session):
    assert len(full_session.descriptors) == 10
    rms = [d.rms_mean for d in full_session.descriptors]
    assert all(v is not None and v > 0 for v in rms)
    # Distinct synthetic content: stems do not share RMS levels.
    assert len({round(v, 4) for v in rms}) >= 8


def test_honesty_warnings_present(full_session):
    assert full_session.source_type == "synthetic_demo"
    assert full_session.metadata["synthetic"] is True
    assert any("synthetic" in w for w in full_session.warnings)


# --------------------------------------------------------------------------- #
# Canonical export: the whole pipeline lights up
# --------------------------------------------------------------------------- #
def test_full_bundle_validates(full_bundle):
    assert full_bundle["result"]["valid"] is True
    assert full_bundle["files"]["validation.json"]["errors"] == []


def test_full_bundle_entity_profile(full_bundle):
    from collections import Counter

    entities = full_bundle["files"]["canonical.snapshot.json"]["entities"]
    counts = Counter(e["entity_type"] for e in entities)
    assert counts["PROJECT"] == 1
    assert counts["TRACK"] == 8
    assert counts["MEDIA_ASSET"] == 10  # 8 stems + mixdown + reference
    assert counts["ANNOTATION"] == 3  # vocal chain, drum bus, piano chain
    assert counts["PROCESSOR"] == 6  # note-asserted plug-ins
    assert counts["OBSERVATION"] == 2  # stem-sum + reference comparison


def test_full_bundle_has_observation_entities(full_bundle):
    snapshot = full_bundle["files"]["canonical.snapshot.json"]
    observations = {
        e["name"]: e
        for e in snapshot["entities"]
        if e["entity_type"] == "OBSERVATION"
    }
    assert set(observations) == {"stem_sum_reconciliation", "reference_comparison"}
    recon = observations["stem_sum_reconciliation"]["properties"]
    assert recon["residual_db"] < -40.0
    assert recon["fitted_gain"] == pytest.approx(demo.FULL_DEMO_MIX_GAIN, abs=1e-3)
    assert observations["reference_comparison"]["properties"]["band_deltas_db"]


def test_full_bundle_evidence_carries_midi_and_musicxml(full_bundle, full_session):
    # In the canonical nested form...
    from logic_session_evidence_explorer.canonical_export import to_canonical

    canonical = to_canonical(full_session)
    assert canonical.evidence.midi_evidence is not None
    assert canonical.evidence.musicxml_evidence is not None
    assert canonical.evidence.stem_sum_reconciliation is not None
    assert len(canonical.evidence.reference_comparisons) == 1
    # ...and flattened into the wire snapshot's extensions payload.
    evidence = full_bundle["files"]["canonical.snapshot.json"]["extensions"][
        "logic_pro"
    ]["evidence"]
    assert set(demo.FULL_DEMO_MIDI_TRACKS) <= set(
        evidence["midi_evidence"]["track_names"]
    )
    assert evidence["musicxml_evidence"]["part_names"] == demo.FULL_DEMO_MUSICXML_PARTS
    # The MIDI/score links ride on the TRACK entities' native payloads.
    linked = [
        e
        for e in full_bundle["files"]["canonical.snapshot.json"]["entities"]
        if e["entity_type"] == "TRACK"
        and (e.get("native") or {}).get("properties", {}).get("linked_midi_track_names")
    ]
    assert linked


def test_full_bundle_descriptors_available(full_bundle):
    descriptors = full_bundle["files"]["canonical.snapshot.json"]["extensions"][
        "logic_pro"
    ]["descriptors"]
    assert len(descriptors) == 10
    assert all(d["available"] is True for d in descriptors)


def test_full_bundle_unknown_plugin_family_stays_unknown(full_bundle):
    """"Warmify Pro" is not in the stock catalogue: no family is invented."""
    processors = {
        e["name"]: e
        for e in full_bundle["files"]["canonical.snapshot.json"]["entities"]
        if e["entity_type"] == "PROCESSOR"
    }
    unknown = processors["Warmify Pro"]["properties"]
    assert unknown.get("family") is None
    assert unknown.get("kind") is None
    known = processors["Space Designer"]["properties"]
    assert known["family"] == "reverb"
    assert known["kind"] == "logic_stock"


def test_full_bundle_honesty_warning_survives_export(full_bundle):
    warnings = full_bundle["files"]["canonical.snapshot.json"]["warnings"]
    assert any("synthetic" in w for w in warnings)


def test_full_bundle_export_is_deterministic(tmp_path, full_session):
    pytest.importorskip("canonical_snapshot")
    from logic_session_evidence_explorer.canonical_export import (
        export_session_bundle,
        exporter,
    )

    a = export_session_bundle(full_session, str(tmp_path / "a"))
    b = export_session_bundle(full_session, str(tmp_path / "b"))
    assert a["snapshot_id"] == b["snapshot_id"]
    for name in exporter.BUNDLE_FILES:
        text_a = open(tmp_path / "a" / name, encoding="utf-8").read()
        text_b = open(tmp_path / "b" / name, encoding="utf-8").read()
        assert text_a == text_b, f"{name} differs between identical exports"


# --------------------------------------------------------------------------- #
# CLI wiring: `export-canonical-bundle demo-full`
# --------------------------------------------------------------------------- #
def test_cli_export_canonical_bundle_demo_full(tmp_path):
    pytest.importorskip("canonical_snapshot")
    out = tmp_path / "bundle"
    # --no-descriptors keeps the wiring test fast; the descriptor path is
    # covered by the module-scoped fixtures above.
    code = cli.main(
        ["export-canonical-bundle", "demo-full", "--out", str(out), "--no-descriptors"]
    )
    assert code == 0
    native = json.load(open(out / "native.json", encoding="utf-8"))
    assert native["model"]["session_name"] == demo.FULL_DEMO_SESSION_NAME
    assert native["model"]["midi_evidence"] is not None
    assert native["model"]["musicxml_evidence"] is not None
