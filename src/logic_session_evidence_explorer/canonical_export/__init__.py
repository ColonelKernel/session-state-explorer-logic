"""The canonical-export adapter: SessionEvidence → v0.2 canonical bundle.

This package is the Logic explorer's side of the "four observation
instruments, one analysis contract" architecture. It maps the repo's native
:class:`~logic_session_evidence_explorer.models.SessionEvidence` into the
nested ``canonical_snapshot`` intermediate (:mod:`.mapper`) and writes the
five-file wire bundle (:mod:`.exporter`):

    adapter_descriptor.json, capabilities.json, native.json,
    canonical.snapshot.json, validation.json

The Logic adapter is deliberately the INFERRED / ANNOTATED / HIDDEN showcase
of the contract: no Logic project file is ever read, so every track is an
evidence reconstruction, every plug-in claim is a user annotation, and the
hidden-state markers become explicit availability records instead of silence.

Requires the ``canonical-snapshot`` package (installed from the analyzer
repo); the rest of this repository keeps working without it.
"""

from .exporter import export_bundle, export_session_bundle
from .mapper import DAW_ID, DIALECT, to_canonical, to_native

__all__ = [
    "DAW_ID",
    "DIALECT",
    "export_bundle",
    "export_session_bundle",
    "to_canonical",
    "to_native",
]
