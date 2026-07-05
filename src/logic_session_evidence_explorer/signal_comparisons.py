"""Signal-level comparisons: stem-sum reconciliation and reference deltas.

Both analyses are plain DSP over the exported audio — no ML, no claim to
recover the processing itself. They exist to *weigh* the hidden-state story
with evidence:

- **Stem-sum reconciliation** sums the aligned stems, fits one global gain to
  the mixdown, and reports the residual. A low residual means the exported
  stems largely explain the mix; a high residual is signal evidence that
  bus/master processing (or missing stems, or misalignment) separates them.
- **Reference comparison** reports per-octave-band energy-fraction deltas
  (level-independent), plus LUFS/crest/width deltas when descriptors carry
  them. It is descriptive: a reference is a comparison, never a target.
"""

from __future__ import annotations

import math
from typing import Optional

from . import utils
from .models import (
    AudioDescriptorSet,
    ReferenceComparison,
    StemSumReconciliation,
)

# Octave-ish analysis bands (Hz). Chosen to match how producers talk about
# spectral balance (lows / low-mids / mids / presence / air).
OCTAVE_BANDS: list[tuple[int, int]] = [
    (60, 120), (120, 250), (250, 500), (500, 1000),
    (1000, 2000), (2000, 4000), (4000, 8000), (8000, 16000),
]

RESIDUAL_TIERS = [
    (-40.0, "The stem sum reconstructs the mixdown closely; little processing "
            "or content is unexplained by the exported stems."),
    (-20.0, "Moderate residual: some bus/master processing, level differences, "
            "or minor content differences separate the stem sum from the mixdown."),
    (math.inf, "Substantial residual: the mixdown contains processing or content "
               "not present in the stem sum — or stems are missing or misaligned."),
]


def _band_label(lo: int, hi: int) -> str:
    return f"{lo}-{hi}Hz"


def _load_mono(path: str, target_sr: Optional[int] = None):
    import librosa

    y, sr = librosa.load(path, sr=target_sr, mono=True)
    return y, sr


def _band_energies(y, sr) -> dict[str, float]:
    import numpy as np

    spec = np.abs(np.fft.rfft(y.astype("float64"))) ** 2
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    energies = {}
    for lo, hi in OCTAVE_BANDS:
        mask = (freqs >= lo) & (freqs < hi)
        energies[_band_label(lo, hi)] = float(spec[mask].sum())
    return energies


def _rms(y) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(y.astype("float64") ** 2)))


def reconcile_stem_sum(
    stem_paths: dict[str, str],
    mixdown_path: str,
    *,
    mixdown_audio_id: str,
) -> StemSumReconciliation:
    """Sum the stems, fit one global gain to the mixdown, report the residual.

    ``stem_paths`` maps audio-evidence ids to file paths. Assumes stems were
    exported full-length and project-start aligned — which in Logic is a
    *choice*, not a default (Range and Include Audio Tail options; see
    ``docs/logic_export_instructions.md``). Duration mismatches are warned
    about and truncated to the shortest signal.
    """

    # Alignment is an export-settings assumption, not a Logic default: the
    # track-export dialog's Range option can trim silence at file end or
    # export only the cycle range, and Include Audio Tail extends files
    # (Logic Pro User Guide pp. 183-186). The warning below names the
    # settings that make stems reconcilable.
    result = StemSumReconciliation(
        id=utils.make_id("reconciliation"),
        mixdown_audio_id=mixdown_audio_id,
        stem_audio_ids=list(stem_paths),
    )
    try:
        import numpy as np

        mix, sr = _load_mono(mixdown_path)
        if mix.size == 0:
            result.warnings.append("Mixdown file is empty; reconciliation skipped.")
            return result

        # Load all stems first and check each against the ORIGINAL mixdown
        # length, so one short stem cannot make later, correctly exported
        # stems look mismatched.
        mix_len = len(mix)
        loaded: list = []
        min_len = mix_len
        for audio_id, path in stem_paths.items():
            y, _sr = _load_mono(path, target_sr=sr)
            if abs(len(y) - mix_len) / max(mix_len, 1) > 0.01:
                result.warnings.append(
                    f"Stem {audio_id} duration differs from the mixdown by more "
                    "than 1%; signals were truncated to the shorter length. For "
                    "a reliable result, export with Range set to extend to the "
                    "project end (not 'Trim Silence at File End' or a cycle "
                    "range) and identical Include Audio Tail settings."
                )
            min_len = min(min_len, len(y))
            loaded.append(y)

        mix = mix[:min_len]
        stem_sum = np.zeros(min_len, dtype="float64")
        for y in loaded:
            stem_sum += y[:min_len].astype("float64")

        sum_energy = float(np.dot(stem_sum, stem_sum))
        if sum_energy <= 0:
            result.warnings.append("Stem sum is silent; reconciliation skipped.")
            return result

        # Least-squares global gain of the stem sum onto the mixdown.
        gain = float(np.dot(stem_sum, mix.astype("float64")) / sum_energy)
        residual = mix.astype("float64") - gain * stem_sum

        mix_rms = _rms(mix)
        if mix_rms <= 0:
            result.warnings.append("Mixdown is silent; reconciliation skipped.")
            return result
        result.fitted_gain = round(gain, 6)
        residual_db = round(20.0 * math.log10(max(_rms(residual), 1e-12) / mix_rms), 2)
        result.residual_db = residual_db if residual_db != 0 else 0.0  # avoid -0.0
        corr = np.corrcoef(stem_sum, mix.astype("float64"))[0, 1]
        result.correlation = round(float(corr), 4) if np.isfinite(corr) else None

        mix_bands = _band_energies(mix, sr)
        res_bands = _band_energies(residual, sr)
        # Clamp the mixdown band energy to a floor of 1e-4 of its total: this
        # bounds the ratio in near-empty mix bands (where two noise-floor
        # energies would produce a meaningless number) while still reporting a
        # large residual in bands the mixdown lacks but the stems fill (e.g. a
        # brick-walled or muted-track bounce).
        mix_total = sum(mix_bands.values()) or 1.0
        floor = 1e-4 * mix_total
        for label, mix_energy in mix_bands.items():
            res_energy = res_bands.get(label, 0.0)
            if res_energy > 0:
                result.band_residuals_db[label] = round(
                    10.0 * math.log10(res_energy / max(mix_energy, floor)), 2
                )

        for threshold, text in RESIDUAL_TIERS:
            if result.residual_db <= threshold:
                result.interpretation = text
                break
    except Exception as exc:
        result.warnings.append(f"Stem-sum reconciliation failed ({exc}).")
    return result


def compare_to_reference(
    mixdown_path: str,
    reference_path: str,
    *,
    mixdown_audio_id: str,
    reference_id: str,
    mixdown_descriptor: Optional[AudioDescriptorSet] = None,
    reference_descriptor: Optional[AudioDescriptorSet] = None,
) -> ReferenceComparison:
    """Describe how the mixdown differs from the reference, band by band.

    Band deltas compare each file's per-band energy *fraction* (level
    independent): positive means the mixdown has proportionally more energy
    in that band than the reference.
    """

    result = ReferenceComparison(
        id=utils.make_id("comparison"),
        mixdown_audio_id=mixdown_audio_id,
        reference_id=reference_id,
    )
    try:
        mix, mix_sr = _load_mono(mixdown_path)
        ref, ref_sr = _load_mono(reference_path)
        if mix.size == 0 or ref.size == 0:
            result.warnings.append("Empty audio; comparison skipped.")
            return result

        mix_bands = _band_energies(mix, mix_sr)
        ref_bands = _band_energies(ref, ref_sr)
        mix_total = sum(mix_bands.values())
        ref_total = sum(ref_bands.values())
        if mix_total <= 0 or ref_total <= 0:
            result.warnings.append("No in-band energy; comparison skipped.")
            return result

        # Clamp fractions to a 1e-4 floor: bounds the delta in bands where one
        # file has essentially no energy (a ratio of noise floors is
        # meaningless, and an unbounded ratio would headline the summary).
        deltas = {}
        for label in mix_bands:
            mix_frac = max(mix_bands[label] / mix_total, 1e-4)
            ref_frac = max(ref_bands[label] / ref_total, 1e-4)
            delta = round(10.0 * math.log10(mix_frac / ref_frac), 2)
            deltas[label] = delta if delta != 0 else 0.0
        result.band_deltas_db = deltas

        def _delta(attr):
            a = getattr(mixdown_descriptor, attr, None) if mixdown_descriptor else None
            b = getattr(reference_descriptor, attr, None) if reference_descriptor else None
            return round(a - b, 2) if a is not None and b is not None else None

        result.lufs_delta = _delta("integrated_loudness_lufs")
        # Prefer the silence-gated crest delta; fall back to whole-file crest
        # only when the gated figure is absent (0.0 is a legitimate delta).
        crest = _delta("dynamic_range_active_db")
        result.crest_delta_db = crest if crest is not None else _delta("dynamic_range_approx")
        result.stereo_width_delta = _delta("stereo_width_ratio")

        if deltas:
            biggest = max(deltas.items(), key=lambda kv: abs(kv[1]))
            direction = "more" if biggest[1] > 0 else "less"
            result.summary = (
                f"Largest spectral difference: the mixdown has "
                f"{abs(biggest[1]):.1f} dB proportionally {direction} energy in "
                f"{biggest[0]} than the reference."
            )
    except Exception as exc:
        result.warnings.append(f"Reference comparison failed ({exc}).")
    return result
