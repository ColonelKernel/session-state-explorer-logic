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
        import numpy as np
    except Exception as exc:  # pragma: no cover - optional dependency
        descriptor.warnings.append(
            f"librosa/numpy not available; descriptors skipped ({exc})."
        )
        return descriptor

    try:
        y, sr = librosa.load(path, sr=None, mono=True)
    except Exception as exc:
        descriptor.warnings.append(f"Could not load audio ({exc}).")
        return descriptor

    if y is None or len(y) == 0:
        descriptor.warnings.append("Audio file is empty.")
        return descriptor

    descriptor.sample_rate = int(sr)
    descriptor.duration_seconds = _safe_float(len(y) / sr)

    try:
        rms = librosa.feature.rms(y=y)[0]
        descriptor.rms_mean = _safe_float(np.mean(rms))
        descriptor.rms_std = _safe_float(np.std(rms))
    except Exception as exc:
        warnings.append(f"RMS failed ({exc}).")

    try:
        peak = float(np.max(np.abs(y)))
        descriptor.peak_amplitude = _safe_float(peak)
        # Rough crest-factor style dynamic-range proxy in dB.
        if descriptor.rms_mean and descriptor.rms_mean > 0 and peak > 0:
            descriptor.dynamic_range_approx = _safe_float(
                20.0 * math.log10(peak / descriptor.rms_mean)
            )
    except Exception as exc:
        warnings.append(f"Peak/dynamic-range failed ({exc}).")

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

    # Optional true loudness measurement.
    try:
        import pyloudnorm as pyln

        meter = pyln.Meter(sr)
        descriptor.integrated_loudness_lufs = _safe_float(meter.integrated_loudness(y))
    except Exception:
        # Silently leave as None: absence of loudness is expected, not an error.
        pass

    descriptor.warnings.extend(warnings)
    return descriptor
