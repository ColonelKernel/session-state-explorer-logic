"""Logic Session Evidence Explorer.

An interpretable DAW-state graph builder that works from the *evidence* a Logic
Pro workflow can export — stems, mixdowns, MIDI, MusicXML and user-provided
channel-strip notes — while making hidden Logic-native state explicit.
"""

from __future__ import annotations

from .models import SCHEMA_VERSION, SessionEvidence

__all__ = ["SCHEMA_VERSION", "SessionEvidence", "__version__"]

__version__ = "0.1.0"
