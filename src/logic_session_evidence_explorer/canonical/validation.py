"""Validation and version gating for canonical snapshots (directive PART 23).

A snapshot must fail *clearly* when loaded under an incompatible schema, and
structural problems (dangling references, bad vocabularies, un-namespaced
extensions) must be reported rather than silently tolerated — research often
begins where observability breaks (directive PART 44).
"""

from __future__ import annotations

from typing import Optional

from ..models import BaseModel, Field
from .schema import (
    AVAILABILITY,
    CANONICAL_SCHEMA_VERSION,
    CAPTURE_MODES,
    ENTITY_KINDS,
    EVIDENCE_LEVELS,
    CanonicalDAWSnapshot,
)

# Same major.minor loads; a different major is incompatible.
SUPPORTED_SCHEMA_VERSIONS = {"0.2.0"}


def _major_minor(version: str) -> tuple[int, int]:
    parts = (version or "").split(".")
    try:
        return int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return (-1, -1)


def is_compatible(version: str) -> bool:
    return _major_minor(version) == _major_minor(CANONICAL_SCHEMA_VERSION)


class ValidationReport(BaseModel):
    ok: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def error(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_snapshot(snapshot: CanonicalDAWSnapshot) -> ValidationReport:
    report = ValidationReport()

    # 1. Version gate.
    if not is_compatible(snapshot.schema_version):
        report.error(
            f"Incompatible schema_version {snapshot.schema_version!r}; this build "
            f"supports {sorted(SUPPORTED_SCHEMA_VERSIONS)}."
        )
        return report  # do not attempt to interpret an incompatible snapshot

    # 2. Required source metadata.
    if not snapshot.source or not snapshot.source.daw:
        report.error("source.daw is required.")
    if snapshot.source and not snapshot.source.adapter:
        report.warn("source.adapter is empty.")
    for mode in (snapshot.source.capture_modes if snapshot.source else []):
        if mode not in CAPTURE_MODES:
            report.warn(f"Unknown capture mode {mode!r}.")

    # 3. Collect all entity ids (incl. project) and check uniqueness.
    entities = list(snapshot.entities.all())
    if snapshot.project is not None:
        entities = [snapshot.project] + entities
    ids: set[str] = set()
    for ent in entities:
        if not ent.id:
            report.error(f"Entity of kind {ent.kind!r} has an empty id.")
            continue
        if ent.id in ids:
            report.error(f"Duplicate entity id {ent.id!r}.")
        ids.add(ent.id)
        if ent.kind not in ENTITY_KINDS:
            report.warn(f"Entity {ent.id!r} has unknown kind {ent.kind!r}.")
        if ent.evidence not in EVIDENCE_LEVELS:
            report.error(f"Entity {ent.id!r} has invalid evidence {ent.evidence!r}.")
        if ent.availability not in AVAILABILITY:
            report.error(f"Entity {ent.id!r} has invalid availability {ent.availability!r}.")
        # Extensions must be namespaced by a non-empty vendor/daw key.
        for ns in ent.extensions:
            if not isinstance(ns, str) or not ns:
                report.error(f"Entity {ent.id!r} has an un-namespaced extension key.")

    # 4. refs must point at known entity ids.
    for ent in entities:
        for role, target in ent.refs.items():
            targets = target if isinstance(target, list) else [target]
            for t in targets:
                if isinstance(t, str) and t and t not in ids:
                    report.warn(f"Entity {ent.id!r} ref {role!r} -> unknown id {t!r}.")

    # 5. Graph: unique node ids; edges reference existing nodes.
    node_ids: set[str] = set()
    for node in snapshot.graph.nodes:
        if node.id in node_ids:
            report.error(f"Duplicate graph node id {node.id!r}.")
        node_ids.add(node.id)
        if node.evidence not in EVIDENCE_LEVELS:
            report.error(f"Graph node {node.id!r} has invalid evidence {node.evidence!r}.")
    for edge in snapshot.graph.edges:
        if edge.source not in node_ids:
            report.error(f"Edge {edge.type!r} source {edge.source!r} is not a graph node.")
        if edge.target not in node_ids:
            report.error(f"Edge {edge.type!r} target {edge.target!r} is not a graph node.")

    return report


def migrate_snapshot(data: dict) -> dict:
    """Migration hook for older canonical payloads. No prior versions exist yet;
    same-version data is returned unchanged, incompatible majors raise."""

    version = data.get("schema_version", "")
    if is_compatible(version):
        return data
    raise ValueError(
        f"Cannot migrate schema_version {version!r} to {CANONICAL_SCHEMA_VERSION}."
    )


__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS", "is_compatible", "ValidationReport",
    "validate_snapshot", "migrate_snapshot",
]
