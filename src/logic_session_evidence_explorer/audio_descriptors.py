"""Audio descriptor extraction using librosa (with graceful degradation).

These are ordinary signal descriptors (RMS, spectral centroid, ZCR, onset
strength, a rough tempo estimate). They characterise the *acoustic outcome* of
a stem, not the DAW processing that produced it. Loudness is reported in LUFS
only when :mod:`pyloudnorm` is available; otherwise it is left ``None`` rather
than reported approximately.
"""

from __future__ import annotations

import math
from typing import Optional

from . import utils
from .models import AudioDescriptorSet


def _safe_float(value) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 6)


def extract_descriptors(
    path: str,
    *,
    source_id: str,
    source_type: str = "audio_evidence",
    file_name: Optional[str] = None,
    estimate_tempo: bool = True,
) -> AudioDescriptorSet:
    """Extract descriptors from an audio file at ``path``.

    Any failure is captured as a warning; the returned object always exists so
    that a single unreadable file never aborts a whole session build.
    """

    file_name = file_name or utils.strip_extension(path)
    warnings: list[str] = []
    descriptor = AudioDescriptorSet(
        id=utils.make_id("descriptor"),
        source_id=source_id,
        source_type=source_type,
        file_name=file_name,
    )

    try:
        import librosa
        # librosa 0.10+ lazy-loads submodules; librosa.feature.rhythm must be
        # imported explicitly or the tempo call below raises AttributeError.
        import librosa.feature.rhythm
        import numpy as np
    except Exception as exc:  # pragma: no cover - optional dependency
        descriptor.warnings.append(
            f"librosa/numpy not available; descriptors skipped ({exc})."
        )
        return descriptor

    try:
        # Load in the file's original channel layout: loudness (BS.1770) and
        # peak must be measured on the real channels, not a mono downmix.
        y_raw, sr = librosa.load(path, sr=None, mono=False)
    except Exception as exc:
        descriptor.warnings.append(f"Could not load audio ({exc}).")
        return descriptor

    if y_raw is None or y_raw.size == 0:
        descriptor.warnings.append("Audio file is empty.")
        return descriptor

    # Spectral/temporal features are computed on a mono mix; y_raw keeps the
    # channel layout for peak and loudness. Remove DC so an offset does not
    # register as activity or crush the crest figure (BS.1770 loudness has its
    # own highpass; sample peak legitimately includes DC).
    y = np.mean(y_raw, axis=0) if y_raw.ndim > 1 else y_raw
    y = y - float(np.mean(y))

    descriptor.sample_rate = int(sr)
    descriptor.duration_seconds = _safe_float(y_raw.shape[-1] / sr)

    try:
        rms = librosa.feature.rms(y=y)[0]
        descriptor.rms_mean = _safe_float(np.mean(rms))
        descriptor.rms_std = _safe_float(np.std(rms))

        # Silence-gated level: Logic exports stems at full song length, so a
        # part that plays in one section is mostly silence and whole-file RMS
        # measures arrangement density, not level. Gate at -60 dBFS.
        silence_threshold = 10.0 ** (-60.0 / 20.0)
        active = rms > silence_threshold
        descriptor.activity_ratio = _safe_float(np.mean(active))
        if active.any():
            descriptor.active_rms_mean = _safe_float(np.mean(rms[active]))
            if descriptor.duration_seconds:
                descriptor.active_duration_seconds = _safe_float(
                    float(np.mean(active)) * descriptor.duration_seconds
                )
    except Exception as exc:
        warnings.append(f"RMS failed ({exc}).")

    try:
        peak = float(np.max(np.abs(y_raw)))
        descriptor.peak_amplitude = _safe_float(peak)
        # Rough crest-factor style dynamic-range proxy in dB, whole-file and
        # silence-gated. The gated variant is the meaningful one for sparse
        # stems (silence inflates the whole-file figure).
        if descriptor.rms_mean and descriptor.rms_mean > 0 and peak > 0:
            descriptor.dynamic_range_approx = _safe_float(
                20.0 * math.log10(peak / descriptor.rms_mean)
            )
        if descriptor.active_rms_mean and descriptor.active_rms_mean > 0 and peak > 0:
            descriptor.dynamic_range_active_db = _safe_float(
                20.0 * math.log10(peak / descriptor.active_rms_mean)
            )
    except Exception as exc:
        warnings.append(f"Peak/dynamic-range failed ({exc}).")

    # Stereo width: RMS of the side signal relative to the mid signal.
    # 0 = dual-mono, ~1 = fully decorrelated; direct observable evidence of
    # printed stereo processing (reverbs, wideners, true-stereo sources).
    try:
        if y_raw.ndim > 1 and y_raw.shape[0] == 2:
            mid = (y_raw[0] + y_raw[1]) / 2.0
            side = (y_raw[0] - y_raw[1]) / 2.0
            mid_rms = float(np.sqrt(np.mean(mid ** 2)))
            side_rms = float(np.sqrt(np.mean(side ** 2)))
            if mid_rms > 0:
                descriptor.stereo_width_ratio = _safe_float(side_rms / mid_rms)
            elif side_rms > 0:
                warnings.append(
                    "Channels are exactly out of phase (no mid signal); stereo "
                    "width ratio is undefined."
                )
    except Exception as exc:
        warnings.append(f"Stereo width failed ({exc}).")

    try:
        descriptor.spectral_centroid_mean = _safe_float(
            np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        )
        descriptor.spectral_bandwidth_mean = _safe_float(
            np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr))
        )
        descriptor.spectral_rolloff_mean = _safe_float(
            np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr))
        )
    except Exception as exc:
        warnings.append(f"Spectral descriptors failed ({exc}).")

    try:
        descriptor.zero_crossing_rate_mean = _safe_float(
            np.mean(librosa.feature.zero_crossing_rate(y=y))
        )
    except Exception as exc:
        warnings.append(f"Zero-crossing-rate failed ({exc}).")

    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        descriptor.onset_strength_mean = _safe_float(np.mean(onset_env))
        if estimate_tempo:
            tempo = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=sr)
            descriptor.estimated_tempo = _safe_float(
                tempo[0] if hasattr(tempo, "__len__") else tempo
            )
    except Exception as exc:
        warnings.append(f"Onset/tempo failed ({exc}).")

    # Optional true loudness measurement (BS.1770 via pyloudnorm), on the
    # file's original channel layout — pyloudnorm expects (samples, channels).
    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sr)
        loudness_input = y_raw.T if y_raw.ndim > 1 else y_raw
        descriptor.integrated_loudness_lufs = _safe_float(
            meter.integrated_loudness(loudness_input)
        )
    except Exception:
        # Silently leave as None: absence of loudness is expected, not an error.
        pass

    descriptor.warnings.extend(warnings)
    return descriptor
