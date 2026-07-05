from logic_session_evidence_explorer import logic_catalog, role_inference


def test_current_plugin_recognised():
    info = logic_catalog.lookup_plugin("Channel EQ")
    assert info.category == "eq"
    assert info.generation == "current"
    # Case-insensitive token matching.
    assert logic_catalog.lookup_plugin("channel eq").name == "Channel EQ"


def test_legacy_plugin_distinguished_from_current():
    assert logic_catalog.lookup_plugin("DeEsser").generation == "legacy"
    assert logic_catalog.lookup_plugin("DeEsser 2").generation == "current"


def test_third_party_plugin_not_recognised():
    assert logic_catalog.lookup_plugin("FabFilter Pro-Q 3") is None
    assert logic_catalog.lookup_plugin("Saturation") is None
    # A bare "EQ" is ambiguous, not a documented plug-in name.
    assert logic_catalog.lookup_plugin("EQ") is None


def test_stock_instrument_names_infer_roles():
    # Logic names tracks after the chosen patch/instrument, so exported stems
    # routinely carry stock instrument names.
    assert role_inference.infer_role("Ultrabeat.wav").role == "Drums"
    assert role_inference.infer_role("Alchemy Take2.wav").role == "Keys"
    assert role_inference.infer_role("Vintage B3.wav").role == "Keys"
    assert role_inference.infer_role("Studio Horns.wav").role == "Brass"
    result = role_inference.infer_role("Sculpture.wav")
    assert result.role == "Keys"
    assert "stock instrument" in result.explanation


def test_ambiguous_instruments_abstain():
    # Sampler/Quick Sampler can host anything: abstention is correct.
    assert role_inference.infer_role("Quick Sampler.wav").role == "Unknown"
    assert role_inference.infer_role("Sampler.wav").role == "Unknown"


def test_keywords_take_precedence_over_instrument_names():
    # An explicit role keyword OUTSIDE the instrument name disambiguates.
    result = role_inference.infer_role("Alchemy Bass.wav")
    assert result.role == "Bass"
    assert result.confidence == 0.75
    assert "keyword" in result.explanation


def test_stock_instrument_name_credited_over_contained_keyword():
    # A documented stock instrument name whose own tokens contain a role
    # keyword (e.g. "Studio Horns" contains "horn") must be credited to the
    # catalog — 0.80 with a named explanation — not shadowed at 0.75 by the
    # bare keyword.
    for name, role in [("Studio Horns", "Brass"), ("Studio Strings", "Strings"),
                       ("Studio Bass", "Bass"), ("Studio Piano", "Keys")]:
        result = role_inference.infer_role(f"{name}.wav")
        assert result.role == role, name
        assert result.confidence == 0.8, name
        assert f"stock instrument name '{name}'" in result.explanation, name


def test_longer_abstaining_name_shadows_contained_instrument():
    # "Sample Alchemy" (abstain) contains "Alchemy" (Keys): the longest match
    # must win or the abstention policy is bypassed.
    assert role_inference.infer_role("Sample Alchemy.wav").role == "Unknown"


def test_instrument_named_bounce_stem_is_not_a_mixdown():
    # infer_role and looks_like_mixdown must agree: a patch-named stem
    # decorated with a weak mixdown word is instrument evidence, not a mix.
    from logic_session_evidence_explorer import stem_scanner

    evidence = stem_scanner.scan_file(
        stem_scanner.ScannedFile(file_name="01_Ultrabeat_Bounce.wav")
    )
    assert evidence.inferred_role == "Drums"
    assert evidence.is_mixdown is False
    assert not role_inference.looks_like_mixdown("Vintage B3 Bounce.wav")
    # Weak keywords still mark mixdowns when no instrument evidence exists.
    assert role_inference.looks_like_mixdown("Final_Mix.wav")


def test_plugin_note_nodes_tagged_in_graph():
    from logic_session_evidence_explorer import (
        graph_builder,
        session_builder,
        stem_scanner,
        utils,
    )
    from logic_session_evidence_explorer.models import ChannelStripNote, SessionEvidence

    utils.reset_ids()
    audio = stem_scanner.scan_files([stem_scanner.ScannedFile(file_name="01_Lead_Vocal.wav")])
    note = ChannelStripNote(
        id="n1", track_name="Lead Vocal", role="Vocal",
        plugins=["Channel EQ", "DeEsser", "FabFilter Pro-Q 3"],
    )
    session = SessionEvidence(session_name="CatalogTest", audio_files=audio,
                              channel_strip_notes=[note])
    session = session_builder.finalize_session(session, with_descriptors=False)
    export = graph_builder.build_graph_export(session)
    plugin_nodes = {n["label"]: n for n in export.nodes if n["type"] == "plugin_note"}
    assert plugin_nodes["Channel EQ"]["plugin_category"] == "eq"
    assert plugin_nodes["Channel EQ"]["plugin_generation"] == "current"
    assert plugin_nodes["DeEsser"]["plugin_generation"] == "legacy"
    assert "plugin_category" not in plugin_nodes["FabFilter Pro-Q 3"]
