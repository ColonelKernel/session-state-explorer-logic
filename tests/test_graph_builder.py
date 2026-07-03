from logic_session_evidence_explorer import graph_builder, session_builder, stem_scanner, utils
from logic_session_evidence_explorer.models import AudioDescriptorSet, SessionEvidence


def _build_session():
    utils.reset_ids()
    names = ["01_Drums.wav", "02_Bass.wav", "05_Lead_Vocal.wav", "Stereo_Mix_Bounce.wav"]
    files = [stem_scanner.ScannedFile(file_name=n) for n in names]
    audio = stem_scanner.scan_files(files)
    session = SessionEvidence(session_name="Test", audio_files=audio)
    session = session_builder.finalize_session(session, with_descriptors=False)
    # Attach a synthetic descriptor to the first non-mixdown audio file.
    first = next(a for a in session.audio_files if not a.is_mixdown)
    desc = AudioDescriptorSet(id=utils.make_id("descriptor"), source_id=first.id,
                              file_name=first.file_name, rms_mean=0.1)
    first.descriptor_id = desc.id
    session.descriptors.append(desc)
    for t in session.inferred_tracks:
        if t.source_audio_id == first.id:
            t.descriptor_id = desc.id
    return session


def test_session_node_exists():
    export = graph_builder.build_graph_export(_build_session())
    types = {n["type"] for n in export.nodes}
    assert "session" in types


def test_audio_evidence_nodes_exist():
    export = graph_builder.build_graph_export(_build_session())
    audio_nodes = [n for n in export.nodes if n["type"] in ("audio_evidence", "mixdown")]
    assert len(audio_nodes) >= 4


def test_inferred_track_nodes_exist():
    export = graph_builder.build_graph_export(_build_session())
    inferred = [n for n in export.nodes if n["type"] == "inferred_track"]
    assert len(inferred) == 3  # mixdown excluded


def test_descriptor_nodes_exist():
    export = graph_builder.build_graph_export(_build_session())
    assert any(n["type"] == "descriptor_set" for n in export.nodes)


def test_hidden_state_marker_nodes_exist():
    export = graph_builder.build_graph_export(_build_session())
    assert any(n["type"] == "hidden_state_marker" for n in export.nodes)


def test_expected_edges_exist():
    export = graph_builder.build_graph_export(_build_session())
    etypes = {e["type"] for e in export.edges}
    assert "contains_audio" in etypes
    assert "infers_track" in etypes
    assert "has_descriptor" in etypes
    assert "has_hidden_state" in etypes


def test_metadata_observability_percentages():
    export = graph_builder.build_graph_export(_build_session())
    pct = export.metadata["observability_percentages"]
    assert abs(sum(pct.values()) - 100.0) < 1.0
