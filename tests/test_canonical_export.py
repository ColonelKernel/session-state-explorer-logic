"""Tests for the canonical-export adapter (v0.2 analyzer wire contract).

Everything here runs without audio dependencies: the demo session is built
with ``with_descriptors=False`` (its design guarantee), and descriptor-mapping
is exercised with a hand-built descriptor. The suite skips cleanly when the
optional ``canonical-snapshot`` package is not installed, matching the repo's
guarded-optional-dependency policy.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("canonical_snapshot")

from canonical_snapshot import nested  # noqa: E402
from canonical_snapshot.models import CanonicalDAWSnapshot, SourceInfo  # noqa: E402
from canonical_snapshot import flatten_session  # noqa: E402

from logic_session_evidence_explorer import demo  # noqa: E402
from logic_session_evidence_explorer.canonical_export import (  # noqa: E402
    exporter,
    mapper,
    export_bundle,
    export_session_bundle,
    to_canonical,
    to_native,
)
from logic_session_evidence_explorer.models import (  # noqa: E402
    AudioDescriptorSet,
    SessionEvidence,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO, "data", "examples")


@pytest.fixture(scope="module")
def demo_session() -> SessionEvidence:
    return demo.build_demo_session(with_descriptors=False)


@pytest.fixture(scope="module")
def canonical(demo_session) -> nested.CanonicalSession:
    return to_canonical(demo_session)


def _source() -> SourceInfo:
    return SourceInfo(
        daw=mapper.DAW_ID,
        adapter=exporter.ADAPTER_NAME,
        adapter_version="test",
        capture_modes=["evidence_scan"],
    )


# --------------------------------------------------------------------------- #
# Mapper: exact round-trip
# --------------------------------------------------------------------------- #
def test_roundtrip_is_exact(demo_session, canonical):
    restored = to_native(canonical)
    assert restored.model_dump() == demo_session.model_dump()


def test_to_native_rejects_foreign_payloads(canonical):
    with pytest.raises(ValueError):
        to_native(nested.CanonicalSession(dialect="logic"))
    foreign = canonical.model_copy(deep=True)
    foreign.native.dialect = "reaper"
    with pytest.raises(ValueError):
        to_native(foreign)


# --------------------------------------------------------------------------- #
# Mapper: inferred tracks
# --------------------------------------------------------------------------- #
def test_inferred_track_mapping(demo_session, canonical):
    assert canonical.dialect == "logic"
    assert canonical.name == demo_session.session_name
    assert canonical.metadata["source_artifact"] == "exported_audio"
    assert canonical.metadata["daw_version"] == demo_session.daw_version
    assert canonical.metadata["source_type"] == "synthetic_demo"

    assert len(canonical.tracks) == len(demo_session.inferred_tracks)
    for track, native in zip(canonical.tracks, demo_session.inferred_tracks):
        assert track.kind == "inferred"
        assert track.id == f"logic:{native.id}"
        assert track.provenance.observability == "inferred"
        assert track.provenance.confidence == native.confidence
        assert track.provenance.source_artifact == "exported_audio"
        # Observed evidence facts stay observed; the heuristic name/role are
        # inferred (track_name maps onto the nested "name" field).
        assert track.field_provenance["file_name"].observability == "observed"
        assert track.field_provenance["name"].observability == "inferred"
        assert track.field_provenance["role"].observability == "inferred"
        # Hidden fields ride along explicitly.
        assert track.extras["hidden_fields"] == native.hidden_fields
        assert track.extras["source_audio_id"] == f"logic:{native.source_audio_id}"


def test_note_lifted_fields_are_annotation_not_inference(demo_session, canonical):
    documented = [
        (track, native)
        for track, native in zip(canonical.tracks, demo_session.inferred_tracks)
        if native.channel_strip_note_ids
    ]
    assert documented, "demo must contain note-documented tracks"
    for track, native in documented:
        for field in ("plugin_chain", "sends", "bus_routing"):
            assert field in native.inferred_fields
            assert track.field_provenance[field].observability == "annotation"
            assert field not in track.extras["hidden_fields"]


# --------------------------------------------------------------------------- #
# Mapper: note-asserted processors
# --------------------------------------------------------------------------- #
def test_note_asserted_plugins_become_annotated_processors(canonical):
    vocal = next(t for t in canonical.tracks if t.name == "Lead Vocal Bounce")
    names = [p.name for p in vocal.processors]
    assert names == ["Channel EQ", "Compressor", "DeEsser 2", "Tape Delay"]
    families = [p.family for p in vocal.processors]
    assert families == ["eq", "dynamics", "dynamics", "delay"]  # via logic_catalog
    for proc in vocal.processors:
        assert proc.provenance.observability == "annotation"
        assert proc.provenance.source_artifact == "channel_strip_note"
        assert proc.kind == "logic_stock"
        assert proc.track_id == vocal.id

    undocumented = next(t for t in canonical.tracks if t.name == "Bass Bounce")
    assert undocumented.processors == []


def test_flattened_processors_carry_annotated_evidence(canonical):
    snapshot = flatten_session(canonical, _source(), default_stability="OFFICIAL_EXPORT")
    processors = snapshot.entities_of_type("PROCESSOR")
    assert processors
    for proc in processors:
        record = snapshot.provenance_by_id(proc.prov["*"])
        assert record.evidence == "ANNOTATED"
        assert record.source_stability == "OFFICIAL_EXPORT"
        assert record.confidence is not None


# --------------------------------------------------------------------------- #
# Mapper: descriptors (documented field rename)
# --------------------------------------------------------------------------- #
def test_descriptor_dynamic_range_rename():
    session = SessionEvidence(
        session_name="Descriptor rename probe",
        descriptors=[
            AudioDescriptorSet(
                id="desc_1",
                source_id="audio_1",
                file_name="stem.wav",
                dynamic_range_approx=12.5,
                rms_mean=0.1,
            )
        ],
    )
    canonical = to_canonical(session)
    (descriptor,) = canonical.descriptors
    assert descriptor.id == "logic:desc_1"
    assert descriptor.source_id == "logic:audio_1"
    assert descriptor.dynamic_range_db == 12.5
    assert descriptor.available is True
    assert not hasattr(descriptor, "dynamic_range_approx")


# --------------------------------------------------------------------------- #
# Exporter: the five-file bundle
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def bundle(tmp_path_factory, demo_session):
    out_dir = tmp_path_factory.mktemp("bundle")
    result = export_session_bundle(demo_session, str(out_dir))
    files = {
        name: json.load(open(os.path.join(str(out_dir), name), encoding="utf-8"))
        for name in exporter.BUNDLE_FILES
    }
    return {"result": result, "files": files, "out_dir": str(out_dir)}


def test_bundle_has_five_files_and_validates(bundle):
    assert sorted(bundle["files"]) == sorted(exporter.BUNDLE_FILES)
    assert bundle["result"]["valid"] is True
    validation = bundle["files"]["validation.json"]
    assert validation["valid"] is True
    assert validation["errors"] == []


def test_bundle_tracks_are_track_only_with_channel_unknown(bundle):
    snapshot = CanonicalDAWSnapshot.model_validate(bundle["files"]["canonical.snapshot.json"])
    tracks = snapshot.entities_of_type("TRACK")
    assert len(tracks) == 6
    assert snapshot.entities_of_type("CHANNEL") == []
    assert snapshot.relationships_of_type("TRACK_USES_CHANNEL") == []
    for track in tracks:
        assert track.availability["channel"] == "UNKNOWN"
        record = snapshot.provenance_by_id(track.prov["*"])
        assert record.evidence == "INFERRED"


def test_bundle_annotation_entities_present(bundle):
    snapshot = CanonicalDAWSnapshot.model_validate(bundle["files"]["canonical.snapshot.json"])
    annotations = snapshot.entities_of_type("ANNOTATION")
    assert {a.name for a in annotations} == {"Lead Vocal", "Drums"}
    for note in annotations:
        record = snapshot.provenance_by_id(note.prov["*"])
        assert record.evidence == "ANNOTATED"


def test_bundle_hidden_markers_become_availability(bundle):
    snapshot = CanonicalDAWSnapshot.model_validate(bundle["files"]["canonical.snapshot.json"])
    project = snapshot.entity_by_id(snapshot.project)
    # Session-level hidden state lands on the PROJECT entity.
    assert project.availability["automation"] == "INACCESSIBLE"
    assert project.availability["routing"] == "INACCESSIBLE"
    assert snapshot.provenance_by_id(project.prov["automation"]).evidence == "HIDDEN"
    # Track-level: plugin_chain is INACCESSIBLE exactly where no note lifted it.
    hidden_chains = {
        e.id
        for e in snapshot.entities_of_type("TRACK")
        if e.availability.get("plugin_chain") == "INACCESSIBLE"
    }
    assert len(hidden_chains) == 4  # 6 stems minus 2 note-documented tracks
    assert any(r.evidence == "HIDDEN" for r in snapshot.provenance)


def test_bundle_has_no_home_dir_paths(bundle):
    home = os.path.expanduser("~")
    for name in exporter.BUNDLE_FILES:
        text = open(os.path.join(bundle["out_dir"], name), encoding="utf-8").read()
        assert home not in text, f"{name} leaks the home directory"


def test_bundle_capabilities_are_honest(bundle):
    caps = bundle["files"]["capabilities.json"]
    assert caps["daw"] == "logic_pro"
    read = caps["read"]
    assert read["structure"]["fields"]["role"]["source_stability"] == "HEURISTIC"
    assert read["audio_content"]["fields"]["audio_content"]["source_stability"] == "OFFICIAL_EXPORT"
    assert read["plugin_chain"]["fields"]["plugin_chain"]["source_stability"] == "MANUAL"
    assert read["automation"]["fields"]["automation"]["support"] == "NONE"
    assert read["mixer_state"]["fields"]["volume_db"]["support"] == "NONE"
    assert caps["write"] == {} and caps["live_observation"] == {} and caps["render"] == {}

    descriptor = bundle["files"]["adapter_descriptor.json"]
    assert descriptor["adapter_id"] == "logic-evidence"
    assert descriptor["write"] == "NONE"
    assert any("99.3%" in item for item in descriptor["known_limitations"])


def test_bundle_native_sidecar_is_referenced_and_roundtrips(bundle, demo_session):
    snapshot = bundle["files"]["canonical.snapshot.json"]
    native = bundle["files"]["native.json"]
    ref = snapshot["extensions"]["logic_pro"]["native_file"]
    assert ref["path"] == "native.json"
    import hashlib

    text = open(os.path.join(bundle["out_dir"], "native.json"), encoding="utf-8").read()
    assert ref["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    restored = SessionEvidence.model_validate(native["model"])
    # Sanitisation rewrites temp paths, so compare the sanitized form.
    expected = exporter.sanitize_session(demo_session)
    assert restored.model_dump() == expected.model_dump()


def test_export_is_deterministic(tmp_path, demo_session):
    a = export_session_bundle(demo_session, str(tmp_path / "a"))
    b = export_session_bundle(demo_session, str(tmp_path / "b"))
    assert a["snapshot_id"] == b["snapshot_id"]
    for name in exporter.BUNDLE_FILES:
        text_a = open(tmp_path / "a" / name, encoding="utf-8").read()
        text_b = open(tmp_path / "b" / name, encoding="utf-8").read()
        assert text_a == text_b, f"{name} differs between identical exports"


def test_export_bundle_from_example_manifest(tmp_path):
    result = export_bundle(
        os.path.join(EXAMPLES, "example_session_manifest.json"),
        str(tmp_path / "bundle"),
        notes_path=os.path.join(EXAMPLES, "example_channel_strip_notes.csv"),
    )
    assert result["valid"] is True
    snapshot = result["snapshot"]
    tracks = snapshot.entities_of_type("TRACK")
    assert {t.name for t in tracks} == {"Lead Vocal Bounce", "Drums Bounce", "Bass Bounce"}
    # Manifest-only build: audio named but absent; still an honest snapshot.
    assert snapshot.entities_of_type("ANNOTATION")  # notes CSV rows
    assert snapshot.entities_of_type("PROCESSOR")  # note-asserted plug-ins
    assert any("manifest only" in w for w in snapshot.warnings)


def test_export_demo_via_input_keyword(tmp_path):
    result = export_bundle("demo", str(tmp_path / "bundle"))
    assert result["valid"] is True
    assert result["snapshot_id"].startswith("logic_pro:sha256:")


# --------------------------------------------------------------------------- #
# Folder mode: MIDI / MusicXML sidecar discovery
# --------------------------------------------------------------------------- #
def _make_evidence_folder(tmp_path):
    """Two real stems plus MIDI / MusicXML / decoy-XML sidecars on disk."""

    folder = tmp_path / "evidence"
    folder.mkdir()
    demo._write_synth_wav(str(folder / "Bass DI.wav"), "tone", 55.0)
    demo._write_synth_wav(str(folder / "Piano.wav"), "tone", 261.0)
    (folder / "session.mid").write_bytes(demo.build_full_demo_midi_bytes())
    (folder / "score.musicxml").write_text(
        demo.build_full_demo_musicxml(), encoding="utf-8"
    )
    # A bare .xml that is NOT MusicXML must never be mistaken for a score.
    (folder / "settings.xml").write_text(
        '<?xml version="1.0"?><plist><dict/></plist>', encoding="utf-8"
    )
    return folder


def test_folder_mode_discovers_midi_and_musicxml_sidecars(tmp_path):
    folder = _make_evidence_folder(tmp_path)
    session = exporter.build_session_from_input(str(folder), with_descriptors=False)

    # A real .mid on disk becomes MidiEvidence (with mido parsed track names;
    # without mido the object still exists and carries the degradation warning).
    assert session.midi_evidence is not None
    assert session.musicxml_evidence is not None
    assert session.musicxml_evidence.part_names == demo.FULL_DEMO_MUSICXML_PARTS

    import importlib.util

    if importlib.util.find_spec("mido") is not None:
        assert "Bass DI" in session.midi_evidence.track_names
        by_name = {t.name: t for t in session.inferred_tracks}
        # Evidence linking ran before finalization: token matching connected
        # the MIDI tracks / score parts to the inferred tracks.
        assert by_name["Bass DI"].linked_midi_track_names == ["Bass DI"]
        assert by_name["Piano"].linked_musicxml_parts == ["Piano"]
    else:
        assert session.midi_evidence.warnings


def test_folder_mode_ignores_non_musicxml_xml(tmp_path):
    folder = tmp_path / "evidence"
    folder.mkdir()
    demo._write_synth_wav(str(folder / "Bass DI.wav"), "tone", 55.0)
    (folder / "settings.xml").write_text(
        '<?xml version="1.0"?><plist><dict/></plist>', encoding="utf-8"
    )
    session = exporter.build_session_from_input(str(folder), with_descriptors=False)
    assert session.midi_evidence is None
    assert session.musicxml_evidence is None


def test_folder_mode_bundle_with_music_sidecars_validates(tmp_path):
    folder = _make_evidence_folder(tmp_path)
    result = export_bundle(str(folder), str(tmp_path / "bundle"))
    assert result["valid"] is True
    native = json.load(
        open(tmp_path / "bundle" / "native.json", encoding="utf-8")
    )
    assert native["model"]["midi_evidence"] is not None
    assert native["model"]["musicxml_evidence"] is not None
