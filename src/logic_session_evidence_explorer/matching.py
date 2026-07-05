"""Shared token-based name matching for evidence linking.

Every place the explorer links two named things — channel-strip notes to
stems, MIDI tracks and score parts to inferred tracks, recommendation rules
checking whether a stem is documented — previously reimplemented its own
substring test with subtly different semantics, so the graph and the
recommendations could disagree about what was linked. This module is the
single matcher they all share.

Matching is deliberately transparent: names are tokenised, generic export
vocabulary ("bounce", "stem", "track") and pure index tokens are ignored, and
the score is the fraction of the smaller identity-token set found in the
larger one. The score doubles as the link confidence carried on graph edges.
"""

from __future__ import annotations

import re

# Tokens that describe the export process rather than the track's identity,
# plus common file extensions that survive tokenisation.
GENERIC_TOKENS = {
    "bounce", "bounced", "print", "printed", "track", "audio",
    "stem", "stems", "export", "exported", "file",
    "wav", "aif", "aiff", "flac", "mp3", "m4a", "ogg",
    "mid", "midi", "xml", "musicxml", "mxl",
}

# Minimum score for two names to be considered linked. High enough that
# sibling tracks sharing most-but-not-all identity tokens ("Lead Vocal Verse"
# vs "Lead Vocal Chorus" at 0.667) do not cross-link.
MATCH_THRESHOLD = 0.75

# Insert a boundary at lower/upper camelCase transitions ("FinalMix",
# "DrumBus") before lowercasing, so concatenated names still tokenize.
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(name: str | None) -> list[str]:
    """Split a name into lowercase tokens.

    Unicode-aware (a Cyrillic or Japanese track name matches itself), splits
    camelCase, and keeps '#'/'+' so note names like "C#" survive.
    """

    spaced = _CAMEL_BOUNDARY.sub("_", name or "").lower()
    parts = re.split(r"[^\w#+]+", spaced)
    return [t for part in parts for t in part.split("_") if t]


def identity_tokens(name: str | None) -> set[str]:
    """Tokens that identify the named thing, with export vocabulary removed.

    Digit tokens are kept: Logic numbers multi-renamed tracks and channel
    strips sequentially ("vox 1", "vox 2" — Logic Pro User Guide pp. 130,
    616), so a trailing digit is identity, not noise. Falls back to
    the raw token set when the name consists only of generic tokens (e.g. a
    file literally named "Bounce.wav")."""

    tokens = tokenize(name)
    identity = {t for t in tokens if t not in GENERIC_TOKENS}
    return identity or set(tokens)


def tokens_equal(a: str, b: str) -> bool:
    """Exact token equality, tolerating a trailing plural 's'."""

    return a == b or a + "s" == b or b + "s" == a


def name_match_confidence(a: str | None, b: str | None) -> float:
    """Score how well two names refer to the same thing, in [0, 1].

    The score is the fraction of the smaller identity-token set matched in the
    larger one, so "Lead Vocal" vs "05_Lead_Vocal_Bounce.wav" scores 1.0 while
    "Lead Vocal" vs "Backing Vocals" scores 0.5.
    """

    ta, tb = identity_tokens(a), identity_tokens(b)
    if not ta or not tb:
        return 0.0
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    matched = sum(1 for t in small if any(tokens_equal(t, u) for u in large))
    return matched / len(small)


def names_match(a: str | None, b: str | None, threshold: float = MATCH_THRESHOLD) -> bool:
    """True when two names are confidently linked."""

    return name_match_confidence(a, b) >= threshold
