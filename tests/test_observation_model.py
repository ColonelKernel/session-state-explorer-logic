from logic_session_evidence_explorer import (
    observation_model,
    session_builder,
    stem_scanner,
    utils,
)
from logic_session_evidence_explorer.models import ChannelStripNote, SessionEvidence


def _session(names, notes=None):
    utils.reset_ids()
    files = [stem_scanner.ScannedFile(file_name=n) for n in names]
    audio = stem_scanner.scan_files(files)
    session = SessionEvidence(session_name="ObsTest", audio_files=audio,
                              channel_strip_notes=notes or [])
    return session_builder.finalize_session(session, with_descriptors=False)


def test_markers_derive_from_model_definitions():
    session = _session(["01_Drums.wav", "02_Bass.wav"])
    emitted_types = {m.hidden_state_type for m in session.hidden_state_markers}
    # Every session-level definition emits exactly one marker.
    for hstype, _d in observation_model.session_level_definitions():
        assert hstype in emitted_types
    # Track-level definitions emit one marker per undocumented track.
    track_markers = [m for m in session.hidden_state_markers
                     if m.hidden_state_type == "hidden_plugin_chain"]
    assert len(track_markers) == 2


def test_marker_completeness_against_model():
    """Every field exported audio hides is either annotated or covered by a
    hidden-state marker — the completeness property the model enables."""

    session = _session(["01_Drums.wav"])
    track = session.inferred_tracks[0]
    covered_fields = set()
    for m in session.hidden_state_markers:
        definition = observation_model.HIDDEN_STATE_DEFINITIONS[m.hidden_state_type]
        covered_fields.add(definition["field"])
    for field in observation_model.OBSERVATION_MODEL["exported_audio"]["hides"]:
        assert (
            field in covered_fields
            or field in track.inferred_fields
            or field in ("sends", "track_stack")  # folded into routing marker
        ), f"hidden field {field} has no marker and no annotation"


def test_note_with_plugins_lifts_plugin_chain_marker():
    note = ChannelStripNote(id="n1", track_name="Drums",
                            plugins=["Channel EQ", "Compressor"])
    session = _session(["01_Drums.wav", "02_Bass.wav"], notes=[note])
    plugin_markers = [m for m in session.hidden_state_markers
                      if m.hidden_state_type == "hidden_plugin_chain"]
    # Only the undocumented Bass track keeps its marker.
    assert len(plugin_markers) == 1
    bass_track = next(t for t in session.inferred_tracks if t.role == "Bass")
    assert plugin_markers[0].target_id == bass_track.id


def test_note_without_plugins_does_not_lift_plugin_chain():
    # A note that only names a bus documents routing, not the plug-in chain.
    note = ChannelStripNote(id="n1", track_name="Drums", bus="Drum Bus")
    session = _session(["01_Drums.wav"], notes=[note])
    track = session.inferred_tracks[0]
    assert "plugin_chain" in track.hidden_fields
    assert "bus_routing" not in track.hidden_fields
    assert any(m.hidden_state_type == "hidden_plugin_chain"
               for m in session.hidden_state_markers)


def test_possible_sources_come_from_model():
    session = _session(["01_Drums.wav"])
    for m in session.hidden_state_markers:
        assert m.possible_sources == observation_model.POSSIBLE_SOURCES


def test_prov_export_grounds_graph():
    from logic_session_evidence_explorer import export

    note = ChannelStripNote(id="n1", track_name="Drums", plugins=["EQ"])
    session = _session(["01_Drums.wav", "Stereo_Mix_Bounce.wav"], notes=[note])
    prov = export.prov_json(session)
    assert "prov" in prov["prefix"]
    # Every graph node appears as an entity.
    from logic_session_evidence_explorer import graph_builder
    graph = graph_builder.build_graph_export(session)
    assert len(prov["entity"]) == len(graph.nodes)
    # Hidden markers carry the honest extension type.
    hidden = [e for e in prov["entity"].values()
              if e["lsee:observability"] == "hidden"]
    assert hidden and all(e["prov:type"] == "lsee:HiddenState" for e in hidden)
    # The note is attributed to the producer.
    assert any(a["prov:agent"] == "lsee:producer" for a in prov["wasAttributedTo"])
    # Serializable.
    import json
    json.loads(utils.dumps(prov))
