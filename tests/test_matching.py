from logic_session_evidence_explorer.matching import (
    identity_tokens,
    name_match_confidence,
    names_match,
    tokenize,
)


def test_tokenize_splits_on_separators():
    assert tokenize("01_Lead_Vocal_Bounce.wav") == ["01", "lead", "vocal", "bounce", "wav"]
    assert tokenize("Track 03 - Bass") == ["track", "03", "bass"]
    assert tokenize(None) == []


def test_identity_tokens_drop_generic():
    assert identity_tokens("01_Lead_Vocal_Bounce.wav") == {"01", "lead", "vocal"}
    assert identity_tokens("Drums Bounce") == {"drums"}
    # A name made only of generic tokens falls back to its raw tokens.
    assert identity_tokens("Bounce") == {"bounce"}


def test_note_name_matches_decorated_stem_name():
    # The exact case that made the graph and the vocal rule disagree.
    assert names_match("Lead Vocal", "Lead Vocal Bounce")
    assert name_match_confidence("Lead Vocal", "Lead Vocal Bounce") == 1.0
    assert names_match("Drums", "01_Drums_Bounce.wav")


def test_partial_overlap_does_not_match():
    assert not names_match("Lead Vocal", "Backing Vocals Bounce")
    assert not names_match("Drums", "Bass Bounce")
    assert name_match_confidence("Drums", "Bass Bounce") == 0.0


def test_plural_tolerance():
    assert names_match("Backing Vocal", "Backing Vocals Bounce")


def test_empty_names_never_match():
    assert not names_match("", "Drums")
    assert not names_match(None, None)


def test_numbered_siblings_do_not_cross_match():
    # Logic's default naming for duplicated tracks: the digit is identity.
    assert not names_match("Guitar 1", "Guitar 2")
    assert names_match("Guitar 1", "10_Guitar_1_Bounce.wav")
    assert not names_match("Guitar 1", "11_Guitar_2_Bounce.wav")
    assert not names_match("Harmony 1", "Harmony 2")


def test_word_qualified_siblings_do_not_cross_match():
    assert names_match("Lead Vocal Verse", "Lead Vocal Verse Bounce")
    assert not names_match("Lead Vocal Verse", "Lead Vocal Chorus")


def test_digit_identity_names_match():
    assert names_match("808", "Sub 808")


def test_camelcase_names_tokenize():
    assert tokenize("FinalMix.wav") == ["final", "mix", "wav"]
    assert names_match("LeadVocal", "Lead Vocal Bounce")


def test_non_ascii_names_match_themselves():
    assert names_match("Вокал", "Вокал")
    assert names_match("ボーカル", "ボーカル Bounce")
