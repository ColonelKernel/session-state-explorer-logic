"""Filename-based track-role inference.

Role inference here is deliberately transparent: it is keyword matching over
normalised filenames, and every result carries a confidence score and a
human-readable explanation. It makes no claim about the *actual* content of a
stem beyond what its name suggests.

Mixdown detection is split into *strong* and *weak* keywords. Strong keywords
("stereo mix", "master", …) mark a mixdown outright. Weak keywords ("mix",
"bounce") only mark a mixdown when the filename carries no instrument-role
keyword — this is what lets ``05_Lead_Vocal_Bounce.wav`` be read as a vocal
stem rather than a full mix, even though Logic names bounced stems "…Bounce".
"""

from __future__ import annotations

from dataclasses import dataclass

# Instrument / production-role keywords, checked in order.
INSTRUMENT_ROLE_KEYWORDS: dict[str, list[str]] = {
    "Vocal": ["backing vocal", "lead vox", "vocal", "vox", "voice", "bgv", "harmony"],
    "Drums": ["drums", "drum", "kick", "snare", "hihat", "hi-hat", "hat", "tom", "percussion", "perc", "beat"],
    "Bass": ["bass", "sub", "808"],
    "Guitar": ["electric guitar", "acoustic guitar", "guitar", "gtr"],
    "Keys": ["keys", "piano", "rhodes", "organ", "synth", "pad", "lead synth"],
    "Strings": ["strings", "violin", "viola", "cello"],
    "Brass": ["brass", "trumpet", "trombone", "horn"],
    "FX": ["riser", "impact", "sweep", "texture", "noise", "fx"],
    "Bus": ["bus", "group", "aux", "stem"],
}

STRONG_MIXDOWN_KEYWORDS = ["full mix", "stereo mix", "mixdown", "master", "stereo", "final"]
WEAK_MIXDOWN_KEYWORDS = ["mix", "bounce"]
MIXDOWN_KEYWORDS = STRONG_MIXDOWN_KEYWORDS + WEAK_MIXDOWN_KEYWORDS
REFERENCE_KEYWORDS = ["reference", "ref", "target"]

# Convenience mapping mirroring the spec's keyword table (used for docs/tests).
ROLE_KEYWORDS: dict[str, list[str]] = {
    "Mixdown": MIXDOWN_KEYWORDS,
    "Reference": REFERENCE_KEYWORDS,
    **INSTRUMENT_ROLE_KEYWORDS,
}


@dataclass
class RoleInferenceResult:
    role: str
    confidence: float
    explanation: str
    matched_keyword: str | None = None


def _search(text: str, keywords: list[str]) -> str | None:
    for kw in keywords:
        if kw in text:
            return kw
    return None


def _find_instrument_role(text: str) -> tuple[str, str] | None:
    for role, keywords in INSTRUMENT_ROLE_KEYWORDS.items():
        kw = _search(text, keywords)
        if kw:
            return role, kw
    return None


def looks_like_mixdown(file_name: str) -> bool:
    text = file_name.lower()
    if _search(text, REFERENCE_KEYWORDS):
        return False
    if _search(text, STRONG_MIXDOWN_KEYWORDS):
        return True
    if _search(text, WEAK_MIXDOWN_KEYWORDS) and _find_instrument_role(text) is None:
        return True
    return False


def looks_like_reference(file_name: str) -> bool:
    return _search(file_name.lower(), REFERENCE_KEYWORDS) is not None


def infer_role(file_name: str) -> RoleInferenceResult:
    """Infer a production role from a filename.

    Returns an ``Unknown`` result with low confidence when nothing matches.
    """

    text = file_name.lower()

    # 1. Reference takes precedence.
    ref_kw = _search(text, REFERENCE_KEYWORDS)
    if ref_kw:
        return RoleInferenceResult("Reference", 0.7,
                                   f"Filename contains reference keyword '{ref_kw}'.", ref_kw)

    # 2. Strong mixdown keywords.
    strong = _search(text, STRONG_MIXDOWN_KEYWORDS)
    if strong:
        return RoleInferenceResult("Mixdown", 0.75,
                                   f"Filename contains mixdown keyword '{strong}'.", strong)

    # 3. Instrument / production role.
    instrument = _find_instrument_role(text)
    if instrument:
        role, kw = instrument
        confidence = 0.85 if " " in kw else 0.75
        return RoleInferenceResult(role, confidence,
                                   f"Filename contains {role.lower()} keyword '{kw}'.", kw)

    # 4. Weak mixdown keywords (only reached when no instrument role matched).
    weak = _search(text, WEAK_MIXDOWN_KEYWORDS)
    if weak:
        return RoleInferenceResult("Mixdown", 0.55,
                                   f"Filename contains mixdown keyword '{weak}' and no instrument keyword.", weak)

    return RoleInferenceResult("Unknown", 0.2,
                               "No known role keyword matched the filename.", None)
