"""Small shared helpers: id generation, filename normalisation, JSON I/O."""

from __future__ import annotations

import json
import os
import re
from typing import Any

AUDIO_EXTENSIONS = {".wav", ".aif", ".aiff", ".flac", ".mp3", ".m4a", ".ogg"}

# Deterministic, monotonically increasing id counters keyed by prefix. We avoid
# random / time-based ids so that repeated runs and tests are reproducible.
_ID_COUNTERS: dict[str, int] = {}


def reset_ids() -> None:
    """Reset id counters. Useful at the start of a fresh session build/test."""

    _ID_COUNTERS.clear()


def make_id(prefix: str) -> str:
    """Return a stable, sequential id such as ``audio_1``."""

    _ID_COUNTERS[prefix] = _ID_COUNTERS.get(prefix, 0) + 1
    return f"{prefix}_{_ID_COUNTERS[prefix]}"


def strip_extension(file_name: str) -> str:
    base = os.path.basename(file_name)
    stem, _ext = os.path.splitext(base)
    return stem


def is_audio_file(file_name: str) -> bool:
    _stem, ext = os.path.splitext(file_name.lower())
    return ext in AUDIO_EXTENSIONS


def normalize_track_name(file_name: str) -> str:
    """Turn ``01_Lead_Vocal_Bounce.wav`` into ``Lead Vocal Bounce``.

    Leading numeric index tokens and common separators are removed so that the
    resulting label is human readable. This is a *display* normalisation; the
    original file name is always preserved on the evidence object.
    """

    stem = strip_extension(file_name)
    # Drop a leading index like "01_", "1 - ", "Track 03 ".
    stem = re.sub(r"^\s*track\s*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"^\s*\d+\s*[-_.)\]]*\s*", "", stem)
    # Replace separators with spaces and collapse whitespace.
    stem = re.sub(r"[_\-.]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or strip_extension(file_name)


def infer_track_index(file_name: str) -> int | None:
    """Extract a track index from filenames like ``01_..``, ``1 - ..``,
    ``Track 03 ..``. Returns ``None`` when no leading index is present."""

    stem = strip_extension(file_name)
    m = re.match(r"^\s*track\s*(\d+)", stem, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.match(r"^\s*(\d+)\s*[-_.)\]]", stem)
    if m:
        return int(m.group(1))
    m = re.match(r"^\s*(\d+)\s+\S", stem)
    if m:
        return int(m.group(1))
    return None


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def dumps(obj: Any, indent: int = 2) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)


def write_json(path: str, obj: Any, indent: int = 2) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dumps(obj, indent=indent))
