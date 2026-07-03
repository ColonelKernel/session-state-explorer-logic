import numpy as np
import pytest

from logic_session_evidence_explorer import audio_descriptors, utils

sf = pytest.importorskip("soundfile")
pytest.importorskip("librosa")


def _write_click_track(path, *, sr=44100, duration=3.0, bpm=120.0):
    """Write a WAV of short clicks at a fixed tempo."""
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click = np.hanning(256).astype(np.float32)
    step = int(sr * 60.0 / bpm)
    for start in range(0, len(y) - len(click), step):
        y[start : start + len(click)] += click
    sf.write(path, y, sr)


def test_tempo_estimated_without_onset_warning(tmp_path):
    # Regression: librosa 0.10+ lazy-loads librosa.feature.rhythm, so tempo
    # estimation raised AttributeError and every descriptor carried an
    # "Onset/tempo failed" warning.
    utils.reset_ids()
    wav = tmp_path / "click.wav"
    _write_click_track(wav)

    descriptor = audio_descriptors.extract_descriptors(str(wav), source_id="src-1")

    assert descriptor.estimated_tempo is not None
    assert not any("Onset/tempo failed" in w for w in descriptor.warnings)


def test_descriptors_extracted_from_click_track(tmp_path):
    utils.reset_ids()
    wav = tmp_path / "click.wav"
    _write_click_track(wav)

    descriptor = audio_descriptors.extract_descriptors(str(wav), source_id="src-1")

    assert descriptor.sample_rate == 44100
    assert descriptor.duration_seconds == pytest.approx(3.0, abs=0.01)
    assert descriptor.rms_mean is not None
    assert descriptor.onset_strength_mean is not None
