"""Scan exported audio files into :class:`AudioEvidence` objects.

A "scan" here only reads the *filename* and, where possible, lightweight audio
header info (duration, sample rate). It does not decode full audio; descriptor
extraction is a separate, heavier step in :mod:`audio_descriptors`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import role_inference, utils
from .models import AudioEvidence


@dataclass
class ScannedFile:
    """A file to scan: either a real path or an in-memory upload."""

    file_name: str
    file_path: str | None = None
    upload_name: str | None = None


def _read_audio_header(path: str | None) -> tuple[float | None, int | None, list[str]]:
    """Best-effort duration / sample-rate read using soundfile.

    Returns ``(duration_seconds, sample_rate, warnings)``. Never raises.
    """

    warnings: list[str] = []
    if not path or not os.path.exists(path):
        return None, None, warnings
    try:
        import soundfile as sf

        info = sf.info(path)
        duration = float(info.frames) / info.samplerate if info.samplerate else None
        return duration, int(info.samplerate), warnings
    except Exception as exc:  # pragma: no cover - depends on optional backend
        warnings.append(f"Could not read audio header ({exc}).")
        return None, None, warnings


def scan_file(scanned: ScannedFile, *, force_reference: bool = False) -> AudioEvidence:
    """Turn a single file into an :class:`AudioEvidence` object."""

    file_name = scanned.file_name
    role_result = role_inference.infer_role(file_name)
    is_mixdown = role_inference.looks_like_mixdown(file_name)
    is_reference = force_reference or role_inference.looks_like_reference(file_name)

    # A file flagged as a reference should not also be reported as a mixdown.
    if is_reference:
        is_mixdown = False

    duration, sample_rate, warnings = _read_audio_header(scanned.file_path)

    inferred_name = utils.normalize_track_name(file_name)
    track_index = utils.infer_track_index(file_name)

    role = role_result.role
    explanation = role_result.explanation
    if force_reference:
        role = "Reference"
        explanation = "Marked as a reference track by the user."

    return AudioEvidence(
        id=utils.make_id("audio"),
        file_name=file_name,
        file_path=scanned.file_path,
        upload_name=scanned.upload_name,
        inferred_track_name=inferred_name,
        inferred_role=role,
        role_explanation=explanation,
        is_mixdown=is_mixdown,
        is_reference=is_reference,
        track_index=track_index,
        duration_seconds=duration,
        sample_rate=sample_rate,
        confidence=role_result.confidence,
        warnings=warnings,
    )


def scan_files(
    files: list[ScannedFile],
    *,
    reference_names: set[str] | None = None,
) -> list[AudioEvidence]:
    """Scan many files, sorted by any inferred track index then name."""

    reference_names = reference_names or set()
    evidence = [
        scan_file(f, force_reference=f.file_name in reference_names) for f in files
    ]
    evidence.sort(
        key=lambda e: (
            e.track_index if e.track_index is not None else 10_000,
            e.file_name.lower(),
        )
    )
    return evidence


def scan_paths(paths: list[str], *, reference_names: set[str] | None = None) -> list[AudioEvidence]:
    """Convenience wrapper for scanning a list of filesystem paths."""

    scanned = [
        ScannedFile(file_name=os.path.basename(p), file_path=p) for p in paths
    ]
    return scan_files(scanned, reference_names=reference_names)


def scan_folder(folder: str) -> list[AudioEvidence]:
    """Scan every audio file directly inside ``folder`` (non-recursive)."""

    paths = [
        os.path.join(folder, name)
        for name in sorted(os.listdir(folder))
        if utils.is_audio_file(name)
    ]
    return scan_paths(paths)
