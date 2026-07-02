"""Loaders for optional external evidence: session manifests and channel-strip
notes (CSV or JSON).

Both loaders are tolerant: unknown fields produce warnings but never crash the
build. Channel-strip notes are always treated as *user-provided annotations*,
not extracted Logic-native state.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from . import utils
from .models import ChannelStripNote

KNOWN_MANIFEST_FIELDS = {
    "schema_version",
    "session_name",
    "daw_name",
    "daw_version",
    "audio_files",
    "notes",
    "source_type",
}
KNOWN_MANIFEST_AUDIO_FIELDS = {"file_name", "role", "notes"}
NOTE_COLUMNS = ["track_name", "role", "plugins", "sends", "bus", "notes"]


def _split_list(value: str | None) -> list[str]:
    """Split a semicolon-separated cell into a clean list."""

    if not value:
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


# --------------------------------------------------------------------------- #
# Session manifest
# --------------------------------------------------------------------------- #
class ManifestResult:
    """Parsed manifest plus a per-filename role/notes override map."""

    def __init__(self) -> None:
        self.session_name: str | None = None
        self.daw_name: str | None = None
        self.daw_version: str | None = None
        self.source_type: str | None = None
        self.notes: str | None = None
        self.role_overrides: dict[str, str] = {}
        self.note_overrides: dict[str, str] = {}
        self.warnings: list[str] = []


def load_manifest_dict(data: dict[str, Any]) -> ManifestResult:
    result = ManifestResult()
    if not isinstance(data, dict):
        result.warnings.append("Manifest is not a JSON object; ignored.")
        return result

    for key in data:
        if key not in KNOWN_MANIFEST_FIELDS:
            result.warnings.append(f"Unknown manifest field '{key}' ignored.")

    result.session_name = data.get("session_name")
    result.daw_name = data.get("daw_name")
    result.daw_version = data.get("daw_version")
    result.source_type = data.get("source_type")
    result.notes = data.get("notes")

    for entry in data.get("audio_files", []) or []:
        if not isinstance(entry, dict):
            result.warnings.append("An audio_files entry was not an object; skipped.")
            continue
        for key in entry:
            if key not in KNOWN_MANIFEST_AUDIO_FIELDS:
                result.warnings.append(
                    f"Unknown audio_files field '{key}' ignored."
                )
        file_name = entry.get("file_name")
        if not file_name:
            result.warnings.append("An audio_files entry has no file_name; skipped.")
            continue
        if entry.get("role"):
            result.role_overrides[file_name] = entry["role"]
        if entry.get("notes"):
            result.note_overrides[file_name] = entry["notes"]

    return result


def load_manifest_text(text: str) -> ManifestResult:
    try:
        data = json.loads(text)
    except Exception as exc:
        result = ManifestResult()
        result.warnings.append(f"Could not parse manifest JSON ({exc}).")
        return result
    return load_manifest_dict(data)


def load_manifest_path(path: str) -> ManifestResult:
    with open(path, "r", encoding="utf-8") as fh:
        return load_manifest_text(fh.read())


# --------------------------------------------------------------------------- #
# Channel-strip notes
# --------------------------------------------------------------------------- #
def _note_from_row(row: dict[str, Any]) -> ChannelStripNote:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    return ChannelStripNote(
        id=utils.make_id("note"),
        track_name=str(lower.get("track_name") or lower.get("track") or "").strip(),
        role=(str(lower["role"]).strip() if lower.get("role") else None),
        plugins=_split_list(lower.get("plugins")),
        sends=_split_list(lower.get("sends")),
        bus=(str(lower["bus"]).strip() if lower.get("bus") else None),
        notes=(str(lower["notes"]).strip() if lower.get("notes") else None),
        confidence=0.5,
    )


def load_channel_strip_notes_csv(text: str) -> tuple[list[ChannelStripNote], list[str]]:
    warnings: list[str] = []
    notes: list[ChannelStripNote] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            note = _note_from_row(row)
            if note.track_name:
                notes.append(note)
            else:
                warnings.append("Skipped a notes row with no track_name.")
    except Exception as exc:
        warnings.append(f"Could not parse channel-strip notes CSV ({exc}).")
    return notes, warnings


def load_channel_strip_notes_json(text: str) -> tuple[list[ChannelStripNote], list[str]]:
    warnings: list[str] = []
    notes: list[ChannelStripNote] = []
    try:
        data = json.loads(text)
    except Exception as exc:
        return [], [f"Could not parse channel-strip notes JSON ({exc})."]

    if isinstance(data, dict):
        data = data.get("channel_strip_notes") or data.get("notes") or []
    if not isinstance(data, list):
        return [], ["Channel-strip notes JSON must be a list of objects."]

    for entry in data:
        if not isinstance(entry, dict):
            warnings.append("Skipped a non-object notes entry.")
            continue
        # Support both list and semicolon-string forms for plugins/sends.
        for key in ("plugins", "sends"):
            if isinstance(entry.get(key), list):
                entry[key] = "; ".join(str(x) for x in entry[key])
        note = _note_from_row(entry)
        if note.track_name:
            notes.append(note)
        else:
            warnings.append("Skipped a notes entry with no track_name.")
    return notes, warnings


def load_channel_strip_notes(text: str, *, file_name: str = "") -> tuple[list[ChannelStripNote], list[str]]:
    """Dispatch on file extension / content to CSV or JSON parsing."""

    stripped = text.lstrip()
    if file_name.lower().endswith(".json") or stripped.startswith(("[", "{")):
        return load_channel_strip_notes_json(text)
    return load_channel_strip_notes_csv(text)
