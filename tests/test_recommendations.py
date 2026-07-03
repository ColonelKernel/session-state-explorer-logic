from logic_session_evidence_explorer import recommendations, session_builder, stem_scanner, utils
from logic_session_evidence_explorer.models import (
    ChannelStripNote,
    ReferenceTrackEvidence,
    SessionEvidence,
)


def _session(names, notes=None, reference_tracks=None):
    utils.reset_ids()
    files = [stem_scanner.ScannedFile(file_name=n) for n in names]
    audio = stem_scanner.scan_files(files)
    session = SessionEvidence(session_name="Test", audio_files=audio,
                              channel_strip_notes=notes or [])
    if reference_tracks:
        session.reference_tracks.extend(reference_tracks)
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


def test_dedicated_reference_suppresses_reference_recommendation():
    ref = ReferenceTrackEvidence(id="ref_test", file_name="my_favorite_song.wav")
    session = _session(["01_Drums.wav", "Stereo_Mix_Bounce.wav"],
                       reference_tracks=[ref])
    assert not any("Reference-aware" in t for t in _titles(session))


def test_documented_vocal_stem_does_not_fire_vocal_rule():
    # Note name "Lead Vocal" must match the decorated stem name
    # "Lead Vocal Bounce" — the exact mismatch the old exact-set logic had.
    note = ChannelStripNote(id="note_test", track_name="Lead Vocal", role="Vocal",
                            plugins=["Channel EQ", "Compressor"])
    session = _session(["05_Lead_Vocal_Bounce.wav", "01_Drums_Bounce.wav"],
                       notes=[note])
    assert not any("Vocal processing" in t for t in _titles(session))


def test_vocal_rule_lists_only_undocumented_stems():
    note = ChannelStripNote(id="note_test", track_name="Lead Vocal", role="Vocal")
    session = _session(
        ["05_Lead_Vocal_Bounce.wav", "06_Backing_Vocals_Bounce.wav"], notes=[note]
    )
    vocal_recs = [r for r in session.recommendations if "Vocal processing" in r.title]
    assert len(vocal_recs) == 1
    backing = next(a for a in session.audio_files if "Backing" in a.file_name)
    lead = next(a for a in session.audio_files if "Lead" in a.file_name)
    assert backing.id in vocal_recs[0].related_node_ids
    assert lead.id not in vocal_recs[0].related_node_ids


def test_bgv_stem_documented_by_matching_note_is_silent():
    # The note names the stem exactly; the rule must agree with the graph's
    # annotated_by edge even though the note name has no 'vocal' token.
    note = ChannelStripNote(id="note_bgv", track_name="BGV Stack",
                            plugins=["Channel EQ", "DeEsser"])
    session = _session(["BGV_Stack.wav"], notes=[note])
    assert not any("Vocal processing" in t for t in _titles(session))


def test_numbered_sibling_note_does_not_document_other_sibling():
    # A note for "Harmony 1" must not suppress the rule for "Harmony 2".
    note = ChannelStripNote(id="note_h1", track_name="Harmony 1", role="Vocal",
                            plugins=["DeEsser"])
    session = _session(["01_Harmony_1.wav", "02_Harmony_2.wav"], notes=[note])
    vocal_recs = [r for r in session.recommendations if "Vocal processing" in r.title]
    assert len(vocal_recs) == 1
    h2 = next(a for a in session.audio_files if "Harmony_2" in a.file_name)
    h1 = next(a for a in session.audio_files if "Harmony_1" in a.file_name)
    assert h2.id in vocal_recs[0].related_node_ids
    assert h1.id not in vocal_recs[0].related_node_ids


def test_midi_mismatch_rule_agrees_with_graph_link_targets():
    # A MIDI track named 'Master' matches no inferred track (the mixdown is
    # not a link target in the graph), so the rule must flag it.
    from logic_session_evidence_explorer.models import MidiEvidence

    utils.reset_ids()
    files = [stem_scanner.ScannedFile(file_name=n) for n in ["Master.wav", "Kick.wav"]]
    audio = stem_scanner.scan_files(files)
    session = SessionEvidence(session_name="Test", audio_files=audio)
    session.midi_evidence = MidiEvidence(id="midi_test", file_name="song.mid",
                                         track_names=["Master", "Kick"])
    session = session_builder.finalize_session(session, with_descriptors=False)
    assert any("not linked to audio evidence" in t for t in _titles(session))


def test_every_recommendation_is_explainable():
    session = _session(["01_Drums.wav", "02_Bass.wav", "03_Guitar.wav", "05_Lead_Vocal.wav"])
    assert session.recommendations
    for rec in session.recommendations:
        assert rec.explanation and rec.suggested_action and rec.caveat
        assert 0.0 <= rec.confidence <= 1.0
        assert rec.severity in ("info", "suggestion", "warning")
