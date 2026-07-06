"""Write the five-file canonical v0.2 bundle from Logic session evidence.

``export_bundle(input, out_dir)`` accepts an evidence folder, a session
manifest JSON, or the literal ``"demo"``; builds a ``SessionEvidence`` through
the repo's normal :mod:`session_builder` pipeline; maps it through
:mod:`.mapper`; and flattens it into::

    adapter_descriptor.json   # identity card + known limitations
    capabilities.json         # per-mode / per-domain / per-field manifest
    native.json               # the verbatim SessionEvidence payload
    canonical.snapshot.json   # the flat v0.2 wire snapshot
    validation.json           # ValidationReport of the snapshot

Determinism: native ids are reset per build (``utils.reset_ids`` via the
builders), canonical id counters are reset per export, ``created_at`` derives
from the *input's* mtime (never wall-clock now), and ``snapshot_id`` is a
content hash of the snapshot body with the volatile fields blanked — the same
evidence in, the same bundle out.

Sanitisation (default on) rewrites the current user's home directory to ``~``
and the system temp directory to ``$TMPDIR`` in every string of the native
model before mapping, so bundles never leak local account names.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

from canonical_snapshot import flatten_session, validate_snapshot
from canonical_snapshot.capabilities import (
    AdapterDescriptor,
    CapabilityManifest,
    DomainCapability,
    FieldCapability,
)
from canonical_snapshot.ids import reset_id_counters
from canonical_snapshot.models import SourceInfo

from .. import manifest_loader, session_builder, stem_scanner, utils
from ..models import SessionEvidence
from .mapper import DAW_ID, DIALECT, to_canonical

ADAPTER_ID = "logic-evidence"
ADAPTER_NAME = "logic-session-evidence-explorer"
CAPTURE_MODES = ["evidence_scan"]

BUNDLE_FILES = (
    "adapter_descriptor.json",
    "capabilities.json",
    "native.json",
    "canonical.snapshot.json",
    "validation.json",
)

_EPOCH_ISO = "1970-01-01T00:00:00+00:00"


def adapter_version() -> str:
    try:
        from importlib import metadata

        return metadata.version(ADAPTER_NAME)
    except Exception:  # pragma: no cover - editable/uninstalled fallback
        return "0.0.0"


# --------------------------------------------------------------------------- #
# Capability manifest — the honesty showcase
# --------------------------------------------------------------------------- #
def _field(
    support: str,
    capture_method: Optional[str] = None,
    source_stability: Optional[str] = None,
    validation_status: str = "TESTED",
) -> FieldCapability:
    return FieldCapability(
        applicability="APPLICABLE",
        support=support,  # type: ignore[arg-type]
        capture_method=capture_method,
        source_stability=source_stability,  # type: ignore[arg-type]
        validation_status=validation_status,  # type: ignore[arg-type]
    )


def build_capability_manifest(daw_version: Optional[str] = None) -> CapabilityManifest:
    """The Logic adapter's capability manifest: evidence-only, read-only.

    Every claim states its pathway and durability. Structure is INFERRED
    (HEURISTIC filename role inference, benchmarked); audio content is
    OBSERVED (OFFICIAL_EXPORT stems); plug-in chains, sends and bus routing
    are ANNOTATED-only (MANUAL channel-strip notes); automation and mixer
    state are HIDDEN — support NONE, applicability APPLICABLE, which is the
    point. Write, live observation and render are NONE across the board.
    """

    hidden = _field("NONE", validation_status="CLAIMED")
    annotated = _field("PARTIAL", "channel_strip_note", "MANUAL")
    read = {
        "structure": DomainCapability(
            fields={
                "track_name": _field("PARTIAL", "filename_normalization", "HEURISTIC"),
                "role": _field("PARTIAL", "filename_role_inference", "HEURISTIC"),
            }
        ),
        "audio_content": DomainCapability(
            fields={"audio_content": _field("FULL", "exported_audio", "OFFICIAL_EXPORT")}
        ),
        "plugin_chain": DomainCapability(fields={"plugin_chain": annotated}),
        "routing": DomainCapability(
            fields={"sends": annotated, "bus_routing": annotated}
        ),
        "automation": DomainCapability(fields={"automation": hidden}),
        "mixer_state": DomainCapability(
            fields={
                "volume_db": hidden,
                "pan": hidden,
                "mute": hidden,
                "solo": hidden,
            }
        ),
    }
    return CapabilityManifest(
        daw=DAW_ID,
        daw_version=daw_version,
        adapter=ADAPTER_NAME,
        adapter_version=adapter_version(),
        read=read,
        # write / live_observation / render stay empty: support is NONE for
        # every domain — this adapter only ever looks at exported evidence.
        notes=[
            "Evidence-only adapter: no Logic project file is parsed; the DAW is "
            "never observed live, written to, or asked to render.",
            "Role inference is HEURISTIC with calibrated confidences: 99.3% over "
            "6467 weighted filename instances (in-sample vocabulary coverage, not "
            "held-out generalization — see docs/evaluation.md).",
            "Empty write/live_observation/render sections mean support NONE for "
            "every domain, not an unexamined gap.",
        ],
    )


def build_adapter_descriptor() -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id=ADAPTER_ID,
        daw=DAW_ID,
        capture_modes=list(CAPTURE_MODES),
        read=(
            "Evidence-only: exported audio OBSERVED (OFFICIAL_EXPORT); track "
            "structure INFERRED (HEURISTIC, benchmarked); plugin chains, sends "
            "and buses ANNOTATED-only (MANUAL notes); automation and mixer "
            "state HIDDEN."
        ),
        write="NONE",
        live_observation="NONE",
        render="NONE",
        known_limitations=[
            "No Logic project file is read: every TRACK is a reconstruction "
            "from exported evidence, never parsed session state.",
            "Role inference is heuristic; benchmarked at 99.3% accuracy over "
            "6467 weighted filename instances, an in-sample vocabulary-coverage "
            "figure rather than held-out generalization (docs/evaluation.md).",
            "Plug-in chains, sends and bus routing enter only as user "
            "channel-strip notes (ANNOTATED / MANUAL); identity, order and "
            "parameters are never observed.",
            "Automation, mixer state, track stacks and VCA assignments are "
            "HIDDEN: printed into the stems and not recoverable from them.",
            "Mixer channels are never observed: TRACK entities carry "
            "availability channel=UNKNOWN instead of fabricated CHANNELs.",
        ],
    )


# --------------------------------------------------------------------------- #
# Sanitisation
# --------------------------------------------------------------------------- #
def _path_replacements() -> list[tuple[str, str]]:
    home = os.path.expanduser("~")
    tmp = tempfile.gettempdir()
    pairs = []
    for raw, token in ((tmp, "$TMPDIR"), (home, "~")):
        real = os.path.realpath(raw)
        for candidate in (real, raw):
            if candidate and candidate != "/" and (candidate, token) not in pairs:
                pairs.append((candidate, token))
    # Longest prefixes first so $TMPDIR under the home dir sanitises cleanly.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _sanitize_value(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        for old, new in replacements:
            if old in value:
                value = value.replace(old, new)
        return value
    if isinstance(value, dict):
        return {k: _sanitize_value(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v, replacements) for v in value]
    return value


def sanitize_session(session: SessionEvidence) -> SessionEvidence:
    """Rewrite home/temp directory prefixes in every string of the model."""

    data = _sanitize_value(session.model_dump(), _path_replacements())
    return SessionEvidence.model_validate(data)


# --------------------------------------------------------------------------- #
# Session building from CLI-style inputs
# --------------------------------------------------------------------------- #
def _apply_manifest(session: SessionEvidence, manifest_path: str) -> None:
    result = manifest_loader.load_manifest_path(manifest_path)
    if result.session_name:
        session.session_name = result.session_name
    if result.daw_version:
        session.daw_version = result.daw_version
    if result.source_type:
        session.source_type = result.source_type
    session.warnings.extend(result.warnings)
    for audio in session.audio_files:
        if audio.file_name in result.role_overrides:
            audio.inferred_role = result.role_overrides[audio.file_name]
            audio.role_explanation = "Role set by session manifest."
            audio.confidence = max(audio.confidence, 0.9)


def _apply_notes(session: SessionEvidence, notes_path: str) -> None:
    with open(notes_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    notes, warnings = manifest_loader.load_channel_strip_notes(
        text, file_name=os.path.basename(notes_path)
    )
    session.channel_strip_notes = notes
    session.warnings.extend(warnings)


def _find_sidecar(folder: str, needle: str, extensions: tuple[str, ...]) -> Optional[str]:
    for name in sorted(os.listdir(folder)):
        lower = name.lower()
        if needle in lower and lower.endswith(extensions):
            return os.path.join(folder, name)
    return None


def build_session_from_input(
    input_path: str,
    *,
    notes_path: Optional[str] = None,
    with_descriptors: bool = False,
) -> SessionEvidence:
    """Build a finalized SessionEvidence from a folder, manifest, or "demo".

    - folder: scan its audio files; ``*manifest*.json`` / ``*note*.csv|json``
      sidecars are picked up automatically (an explicit ``notes_path`` wins).
    - manifest JSON: evidence listed by file name only — honest degraded
      build with no audio on disk.
    - ``"demo"``: the built-in synthetic demo session (real pipeline, synthetic
      audio, clearly labelled as such).
    """

    if input_path == "demo":
        from .. import demo

        return demo.build_demo_session(with_descriptors=with_descriptors)

    utils.reset_ids()
    if os.path.isdir(input_path):
        session = SessionEvidence(
            session_name=os.path.basename(os.path.abspath(input_path)) or "Logic Exports",
            source_type="logic_exports",
            audio_files=stem_scanner.scan_folder(input_path),
        )
        manifest_path = _find_sidecar(input_path, "manifest", (".json",))
        sidecar_notes = notes_path or _find_sidecar(input_path, "note", (".csv", ".json"))
        if sidecar_notes:
            _apply_notes(session, sidecar_notes)
        if manifest_path:
            _apply_manifest(session, manifest_path)
    elif input_path.lower().endswith(".json"):
        result = manifest_loader.load_manifest_path(input_path)
        file_names = list(result.role_overrides) + [
            f for f in result.note_overrides if f not in result.role_overrides
        ]
        session = SessionEvidence(
            session_name=result.session_name or "Logic Session Manifest",
            source_type=result.source_type or "logic_exports",
            audio_files=stem_scanner.scan_files(
                [stem_scanner.ScannedFile(file_name=name) for name in file_names]
            ),
            warnings=[
                "Built from a session manifest only: audio files are named but "
                "not present, so no audio content was observed.",
            ],
        )
        _apply_manifest(session, input_path)
        if notes_path:
            _apply_notes(session, notes_path)
    else:
        raise ValueError(
            f"Input must be an evidence folder, a manifest .json, or 'demo': {input_path!r}"
        )
    return session_builder.finalize_session(session, with_descriptors=with_descriptors)


# --------------------------------------------------------------------------- #
# Bundle writing
# --------------------------------------------------------------------------- #
def _dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso_from_mtime(path: str) -> str:
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat()


def _created_at_for_session(session: SessionEvidence) -> str:
    """created_at from the newest evidence file's mtime — never wall-clock."""

    mtimes = [
        os.path.getmtime(item.file_path)
        for group in (session.audio_files, session.reference_tracks)
        for item in group
        if item.file_path and os.path.exists(item.file_path)
    ]
    if not mtimes:
        return _EPOCH_ISO
    return datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat()


def export_session_bundle(
    session: SessionEvidence,
    out_dir: str,
    *,
    sanitize: bool = True,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    """Map an assembled SessionEvidence and write the five-file bundle."""

    if created_at is None:
        created_at = _created_at_for_session(session)
    if sanitize:
        session = sanitize_session(session)

    canonical = to_canonical(session)
    native_text = _dumps(canonical.native.model_dump())
    native_sha = _sha256(native_text)

    reset_id_counters()
    source = SourceInfo(
        daw=DAW_ID,
        daw_version=session.daw_version,
        adapter=ADAPTER_NAME,
        adapter_version=adapter_version(),
        capture_modes=list(CAPTURE_MODES),
    )
    capabilities = build_capability_manifest(daw_version=session.daw_version)
    # Stems are official Logic bounces (OFFICIAL_EXPORT); what is *inferred*
    # or *annotated* about them is carried by each record's evidence class
    # and confidence, not by pretending a shakier capture pathway.
    snapshot = flatten_session(
        canonical,
        source,
        capabilities,
        native_file="native.json",
        native_sha256=native_sha,
        default_stability="OFFICIAL_EXPORT",
    )

    # Content-hash snapshot id: blank the volatile fields, hash the rest.
    body = snapshot.model_dump()
    body["snapshot_id"] = ""
    body["created_at"] = ""
    snapshot.snapshot_id = f"{DAW_ID}:sha256:{_sha256(_dumps(body))[:16]}"
    snapshot.created_at = created_at

    report = validate_snapshot(snapshot)

    os.makedirs(out_dir, exist_ok=True)
    outputs = {
        "adapter_descriptor.json": build_adapter_descriptor().model_dump(),
        "capabilities.json": capabilities.model_dump(),
        "canonical.snapshot.json": snapshot.model_dump(),
        "validation.json": report.model_dump(),
    }
    for file_name, payload in outputs.items():
        with open(os.path.join(out_dir, file_name), "w", encoding="utf-8") as fh:
            fh.write(_dumps(payload))
    with open(os.path.join(out_dir, "native.json"), "w", encoding="utf-8") as fh:
        fh.write(native_text)

    return {
        "out_dir": out_dir,
        "files": list(BUNDLE_FILES),
        "snapshot_id": snapshot.snapshot_id,
        "valid": report.valid,
        "validation": report,
        "snapshot": snapshot,
    }


def export_bundle(
    input_path: str,
    out_dir: str,
    *,
    with_descriptors: bool = False,
    sanitize: bool = True,
    notes_path: Optional[str] = None,
) -> dict[str, Any]:
    """Build from an evidence folder / manifest / "demo" and export the bundle."""

    session = build_session_from_input(
        input_path, notes_path=notes_path, with_descriptors=with_descriptors
    )
    created_at = None
    if input_path != "demo" and os.path.isfile(input_path):
        created_at = _iso_from_mtime(input_path)
    return export_session_bundle(
        session, out_dir, sanitize=sanitize, created_at=created_at
    )
