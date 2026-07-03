from logic_session_evidence_explorer import role_inference


def test_vocal_filename_maps_to_vocal():
    result = role_inference.infer_role("05_Lead_Vocal_Bounce.wav")
    assert result.role == "Vocal"
    assert result.confidence > 0.5
    assert "vocal" in result.explanation.lower() or "vox" in result.explanation.lower()


def test_drums_filename_maps_to_drums():
    assert role_inference.infer_role("01_Drums.wav").role == "Drums"
    assert role_inference.infer_role("Kick.aiff").role == "Drums"


def test_bass_filename_maps_to_bass():
    assert role_inference.infer_role("02_Bass_DI.wav").role == "Bass"
    assert role_inference.infer_role("808 sub.wav").role == "Bass"


def test_mixdown_filename_maps_to_mixdown():
    assert role_inference.infer_role("Stereo_Mix_Bounce.wav").role == "Mixdown"
    assert role_inference.looks_like_mixdown("Full Mix Final.wav")


def test_reference_precedence():
    result = role_inference.infer_role("Vocal Reference.wav")
    assert result.role == "Reference"
    assert role_inference.looks_like_reference("target_ref.wav")


def test_unknown_filename_low_confidence():
    result = role_inference.infer_role("random_take_take3.wav")
    assert result.role == "Unknown"
    assert result.confidence <= 0.3


def test_keyword_inside_word_does_not_match():
    # 'ref' inside 'Refrain' must not make this a reference track.
    result = role_inference.infer_role("Refrain_Guitar.wav")
    assert result.role == "Guitar"
    assert not role_inference.looks_like_reference("Refrain_Guitar.wav")


def test_stereo_suffix_on_instrument_stem_is_not_mixdown():
    result = role_inference.infer_role("Acoustic_Guitar_Stereo.wav")
    assert result.role == "Guitar"
    assert not role_inference.looks_like_mixdown("Acoustic_Guitar_Stereo.wav")


def test_final_prefix_on_vocal_stem_is_not_mixdown():
    result = role_inference.infer_role("Final_Vocal_Comp.wav")
    assert result.role == "Vocal"
    assert not role_inference.looks_like_mixdown("Final_Vocal_Comp.wav")


def test_weak_keywords_still_mark_mixdown_without_instrument():
    assert role_inference.infer_role("Final_Mix.wav").role == "Mixdown"
    assert role_inference.looks_like_mixdown("Final_Mix.wav")
    assert role_inference.looks_like_mixdown("Bounce.wav")


def test_camelcase_names_classify():
    assert role_inference.infer_role("FinalMix.wav").role == "Mixdown"
    assert role_inference.infer_role("StereoMix.wav").role == "Mixdown"
    assert role_inference.infer_role("PreMaster_v2.wav").role == "Mixdown"
    assert role_inference.infer_role("DrumBus.wav").role == "Drums"
    assert role_inference.infer_role("LeadVocal.wav").role == "Vocal"


def test_plural_keyword_tolerance():
    assert role_inference.infer_role("06_Backing_Vocals_Bounce.wav").role == "Vocal"
