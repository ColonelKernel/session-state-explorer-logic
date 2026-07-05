"""Portable, DAW-agnostic canonical state layer.

Everything here is independent of Logic acquisition: the schema, validation,
graph projection, cross-DAW matching, diff, and capability metrics. Kept inside
the package for now (directive PART 22: don't force a monorepo), but designed
to be extractable into a standalone ``daw-state-schema`` package later.
"""

from __future__ import annotations

from .schema import CANONICAL_SCHEMA_VERSION, CanonicalDAWSnapshot
from .validation import ValidationReport, validate_snapshot

__all__ = [
    "CANONICAL_SCHEMA_VERSION",
    "CanonicalDAWSnapshot",
    "ValidationReport",
    "validate_snapshot",
]
