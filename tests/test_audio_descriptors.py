import math
import struct
import wave

import numpy as np
import pytest

librosa = pytest.importorskip("librosa")
sf = pytest.importorskip("soundfile")

from logic_session_evidence_explorer import audio_descriptors, utils  # noqa: E402


def _write_stereo_wav(path, *, seconds=1.0, sr=22050, left_gain=0.5, right_gain=0.5):
    n = int(seconds * sr)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            t = i / sr
            left = left_gain * math.sin(2 * math.pi * 440 * t)
            right = right_gain * math.sin(2 * math.pi * 440 * t)
            frames += struct.pack("<hh", int(left * 32767), int(right * 32767))
        wf.writeframes(bytes(frames))


def _write_click_track(path, *, sr=44100, duration=3.0, bpm=120.0):
    """Write a WAV of short clicks at a fixed tempo."""
    y = np.zeros(int(sr * duration), dtype=np.float32)
    click = np.hanning(256).astype(np.float32)
    step = int(sr * 60.0 / bpm)
    for start in range(0, len(y) - len(click), step):
        y[start : start + len(click)] += click
    sf.write(path, y, sr)


def test_stereo_file_duration_uses_samples_not_channels(tmp_path):
    utils.reset_ids()
    path = tmp_path / "stereo_tone.wav"
    _write_stereo_wav(path, seconds=1.0)
    desc = audio_descriptors.extract_descriptors(
        str(path), source_id="audio_test", estimate_tempo=False
    )
    # A (2, n) channel-first array must not be read as 2 samples long.
    assert desc.duration_seconds == pytest.approx(1.0, abs=0.01)
    assert desc.sample_rate == 22050
    assert desc.peak_amplitude == pytest.approx(0.5, abs=0.02)
    assert desc.rms_mean is not None


def test_stereo_loudness_measured_on_real_channels(tmp_path):
    pyln = pytest.importorskip("pyloudnorm")  # noqa: F841
    utils.reset_ids()
    # One channel silent: a mono (L+R)/2 downmix would read ~6 dB lower than
    # the true BS.1770 stereo measurement of this signal.
    quiet_right = tmp_path / "one_sided.wav"
    _write_stereo_wav(quiet_right, left_gain=0.5, right_gain=0.0)
    both = tmp_path / "both_sides.wav"
    _write_stereo_wav(both, left_gain=0.5, right_gain=0.5)

    desc_one = audio_descriptors.extract_descriptors(
        str(quiet_right), source_id="a1", estimate_tempo=False
    )
    desc_both = audio_descriptors.extract_descriptors(
        str(both), source_id="a2", estimate_tempo=False
    )
    assert desc_one.integrated_loudness_lufs is not None
    assert desc_both.integrated_loudness_lufs is not None
    # BS.1770 sums channel energies: both-channel signal reads ~3 dB louder
    # than the one-channel signal. A mono downmix would report ~6 dB.
    delta = desc_both.integrated_loudness_lufs - desc_one.integrated_loudness_lufs
    assert delta == pytest.approx(3.0, abs=0.5)


def test_silence_gated_levels_ignore_arrangement_density(tmp_path):
    import math
    import struct

    # A stem that plays loud for 25% of the file and is silent otherwise:
    # whole-file RMS is dragged down by silence; active RMS is not.
    sr = 22050
    n = sr * 2
    path = tmp_path / "sparse_loud.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            s = 0.8 * math.sin(2 * math.pi * 220 * i / sr) if i < n // 4 else 0.0
            frames += struct.pack("<h", int(s * 32767))
        wf.writeframes(bytes(frames))

    desc = audio_descriptors.extract_descriptors(
        str(path), source_id="a1", estimate_tempo=False
    )
    assert desc.activity_ratio is not None
    assert desc.activity_ratio == pytest.approx(0.25, abs=0.05)
    assert desc.active_rms_mean > desc.rms_mean * 2
    assert desc.active_duration_seconds == pytest.approx(0.5, abs=0.1)
    # Gated crest reflects the playing signal, not the silence.
    assert desc.dynamic_range_active_db < desc.dynamic_range_approx


def test_stereo_width_ratio(tmp_path):
    identical = tmp_path / "mono_ish.wav"
    _write_stereo_wav(identical, left_gain=0.5, right_gain=0.5)
    one_sided = tmp_path / "wide.wav"
    _write_stereo_wav(one_sided, left_gain=0.5, right_gain=0.0)

    narrow = audio_descriptors.extract_descriptors(
        str(identical), source_id="a1", estimate_tempo=False
    )
    wide = audio_descriptors.extract_descriptors(
        str(one_sided), source_id="a2", estimate_tempo=False
    )
    assert narrow.stereo_width_ratio == pytest.approx(0.0, abs=0.01)
    assert wide.stereo_width_ratio == pytest.approx(1.0, abs=0.05)


def test_mono_file_still_works(tmp_path):
    utils.reset_ids()
    from logic_session_evidence_explorer.demo import _write_synth_wav

    path = tmp_path / "mono_tone.wav"
    _write_synth_wav(str(path), "tone", 440.0, seconds=1.0)
    desc = audio_descriptors.extract_descriptors(
        str(path), source_id="audio_test", estimate_tempo=False
    )
    assert desc.duration_seconds == pytest.approx(1.0, abs=0.01)
    assert desc.rms_mean is not None
    assert desc.peak_amplitude is not None


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
