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
