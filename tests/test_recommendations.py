from logic_session_evidence_explorer import recommendations, session_builder, stem_scanner, utils
from logic_session_evidence_explorer.models import SessionEvidence


def _session(names, notes=None):
    utils.reset_ids()
    files = [stem_scanner.ScannedFile(file_name=n) for n in names]
    audio = stem_scanner.scan_files(files)
    session = SessionEvidence(session_name="Test", audio_files=audio,
                              channel_strip_notes=notes or [])
    return session_builder.finalize_session(session, with_descriptors=False)


def _titles(session):
    return [r.title for r in session.recommendations]


def test_stems_without_notes_produce_documentation_recommendation():
    session = _session(["01_Drums.wav", "02_Bass.wav"])
    assert any("channel-strip notes" in t for t in _titles(session))


def test_vocal_stem_without_notes_produces_vocal_recommendation():
    session = _session(["05_Lead_Vocal.wav", "01_Drums.wav"])
    assert any("Vocal processing" in t for t in _titles(session))


def test_mixdown_without_reference_produces_reference_recommendation():
    session = _session(["01_Drums.wav", "Stereo_Mix_Bounce.wav"])
    assert any("Reference-aware" in t for t in _titles(session))


def test_many_stems_without_bus_notes_produces_routing_warning():
    session = _session(
        ["01_Drums.wav", "02_Bass.wav", "03_Guitar.wav", "04_Synth_Pad.wav", "05_Lead_Vocal.wav"]
    )
    assert any("Routing graph" in t for t in _titles(session))


def test_every_recommendation_is_explainable():
    session = _session(["01_Drums.wav", "02_Bass.wav", "03_Guitar.wav", "05_Lead_Vocal.wav"])
    assert session.recommendations
    for rec in session.recommendations:
        assert rec.explanation and rec.suggested_action and rec.caveat
        assert 0.0 <= rec.confidence <= 1.0
        assert rec.severity in ("info", "suggestion", "warning")
