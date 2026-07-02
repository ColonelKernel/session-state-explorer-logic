from logic_session_evidence_explorer import stem_scanner, utils


def _scan(names):
    utils.reset_ids()
    files = [stem_scanner.ScannedFile(file_name=n) for n in names]
    return stem_scanner.scan_files(files)


def test_track_name_normalized():
    utils.reset_ids()
    ev = stem_scanner.scan_file(stem_scanner.ScannedFile(file_name="01_Lead_Vocal_Bounce.wav"))
    assert ev.inferred_track_name == "Lead Vocal Bounce"


def test_track_index_inferred():
    assert utils.infer_track_index("01_Lead_Vocal.wav") == 1
    assert utils.infer_track_index("1 - Drums.wav") == 1
    assert utils.infer_track_index("Track 03 Bass.wav") == 3
    assert utils.infer_track_index("Lead Vocal.wav") is None


def test_mixdown_detected():
    ev = _scan(["Stereo_Mix_Bounce.wav"])[0]
    assert ev.is_mixdown is True
    assert ev.is_reference is False


def test_reference_detected():
    ev = _scan(["Mastering Reference.wav"])[0]
    assert ev.is_reference is True
    assert ev.is_mixdown is False


def test_audio_evidence_objects_created():
    evidence = _scan(["01_Drums.wav", "02_Bass.wav", "05_Lead_Vocal.wav"])
    assert len(evidence) == 3
    ids = {e.id for e in evidence}
    assert len(ids) == 3  # unique ids
    # Sorted by track index.
    assert [e.track_index for e in evidence] == [1, 2, 5]


def test_force_reference_flag():
    utils.reset_ids()
    files = [stem_scanner.ScannedFile(file_name="mystery.wav")]
    ev = stem_scanner.scan_files(files, reference_names={"mystery.wav"})[0]
    assert ev.is_reference is True
    assert ev.inferred_role == "Reference"
