"""Filename-based track-role inference.

Role inference here is deliberately transparent: it is keyword matching over
the *tokens* of a filename, and every result carries a confidence score and a
human-readable explanation. It makes no claim about the actual content of a
stem beyond what its name suggests.

Two design points matter for real-world Logic exports:

1. Matching is token-based, not substring-based, so ``Refrain_Guitar.wav`` is
   a guitar stem (not a "ref"-erence) and ``Take3`` never matches anything.
2. Mixdown detection is split into *strong* and *weak* keywords. Strong
   keywords ("stereo mix", "master", "mixdown") mark a mixdown outright. Weak
   keywords ("mix", "bounce", "stereo", "final") only mark a mixdown when the
   filename carries no instrument-role token — this is what lets
   ``05_Lead_Vocal_Bounce.wav``, ``Acoustic_Guitar_Stereo.wav`` and
   ``Final_Vocal_Comp.wav`` be read as stems, even though Logic and producers
   routinely decorate stem names with "Bounce", "Stereo" and "Final".
"""

from __future__ import annotations

from dataclasses import dataclass

from .matching import tokenize, tokens_equal

# Instrument / production-role keywords, checked in order. The base lists
# follow common Logic naming; the extensions marked "corpus" are generic
# production vocabulary that benchmarking against MedleyDB's instrument
# labels exposed as missing. Note the extensions were selected from misses on
# that same corpus, so the accuracy reported in docs/evaluation.md is
# in-sample vocabulary coverage, not held-out generalization.
INSTRUMENT_ROLE_KEYWORDS: dict[str, list[str]] = {
    "Vocal": ["backing vocal", "lead vox", "vocal", "vox", "voice", "bgv", "harmony",
              # corpus:
              "singer", "vocalist", "rapper", "rap", "choir"],
    "Drums": ["drums", "drum", "kick", "snare", "hihat", "hi-hat", "hat", "tom",
              "percussion", "perc", "beat",
              # corpus:
              "cymbal", "tabla", "tambourine", "clap", "shaker", "timpani", "bongo"],
    "Bass": ["bass", "sub", "808"],
    "Guitar": ["electric guitar", "acoustic guitar", "guitar", "gtr"],
    "Keys": ["keys", "piano", "rhodes", "organ", "synth", "pad", "lead synth",
             # corpus:
             "synthesizer"],
    "Strings": ["strings", "violin", "viola", "cello"],
    "Brass": ["brass", "trumpet", "trombone", "horn",
              # corpus:
              "tuba", "cornet", "euphonium"],
    "FX": ["riser", "impact", "sweep", "texture", "noise", "fx"],
    "Bus": ["bus", "group", "aux", "stem"],
}

STRONG_MIXDOWN_KEYWORDS = ["full mix", "stereo mix", "mixdown", "master"]
WEAK_MIXDOWN_KEYWORDS = ["mix", "bounce", "stereo", "final"]
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


def _search(tokens: list[str], keywords: list[str]) -> str | None:
    """Match keywords against the token list. Multi-word keywords must appear
    as a contiguous token subsequence; individual tokens tolerate a plural
    's' (keyword 'vocal' matches the token 'vocals')."""

    for kw in keywords:
        kw_tokens = tokenize(kw)
        n = len(kw_tokens)
        for i in range(len(tokens) - n + 1):
            if all(tokens_equal(tokens[i + j], kw_tokens[j]) for j in range(n)):
                return kw
    return None


def _find_instrument_role(tokens: list[str]) -> tuple[str, str] | None:
    for role, keywords in INSTRUMENT_ROLE_KEYWORDS.items():
        kw = _search(tokens, keywords)
        if kw:
            return role, kw
    return None


def looks_like_mixdown(file_name: str) -> bool:
    tokens = tokenize(file_name)
    if _search(tokens, REFERENCE_KEYWORDS):
        return False
    if _search(tokens, STRONG_MIXDOWN_KEYWORDS):
        return True
    if _search(tokens, WEAK_MIXDOWN_KEYWORDS):
        # Weak keywords ("bounce", "mix", "stereo", "final") only mark a
        # mixdown when NO instrument evidence is present — neither a role
        # keyword nor a Logic stock instrument name ("Ultrabeat_Bounce.wav"
        # is a drum stem, not a mixdown). Must stay consistent with
        # infer_role's step order.
        from .logic_catalog import instrument_role_in_tokens

        if _find_instrument_role(tokens) is None and instrument_role_in_tokens(tokens) is None:
            return True
    return False


def looks_like_reference(file_name: str) -> bool:
    return _search(tokenize(file_name), REFERENCE_KEYWORDS) is not None


def infer_role(file_name: str) -> RoleInferenceResult:
    """Infer a production role from a filename.

    Returns an ``Unknown`` result with low confidence when nothing matches.
    """

    tokens = tokenize(file_name)

    # 1. Reference takes precedence.
    ref_kw = _search(tokens, REFERENCE_KEYWORDS)
    if ref_kw:
        return RoleInferenceResult("Reference", 0.7,
                                   f"Filename contains reference keyword '{ref_kw}'.", ref_kw)

    # 2. Strong mixdown keywords.
    strong = _search(tokens, STRONG_MIXDOWN_KEYWORDS)
    if strong:
        return RoleInferenceResult("Mixdown", 0.75,
                                   f"Filename contains mixdown keyword '{strong}'.", strong)

    # 3. Instrument / production role.
    instrument = _find_instrument_role(tokens)
    if instrument:
        role, kw = instrument
        confidence = 0.85 if " " in kw else 0.75
        return RoleInferenceResult(role, confidence,
                                   f"Filename contains {role.lower()} keyword '{kw}'.", kw)

    # 3b. Logic stock instrument names. Logic names new tracks after the
    # chosen patch/instrument (User Guide p. 129), so exported stems routinely
    # carry names like "Alchemy" or "Ultrabeat".
    from .logic_catalog import instrument_role_in_tokens

    stock = instrument_role_in_tokens(tokens)
    if stock:
        name, role = stock
        return RoleInferenceResult(
            role, 0.8,
            f"Filename contains the Logic stock instrument name '{name}' "
            "(Logic names tracks after the chosen patch/instrument).",
            name.lower(),
        )

    # 4. Weak mixdown keywords (only reached when no instrument role matched).
    weak = _search(tokens, WEAK_MIXDOWN_KEYWORDS)
    if weak:
        return RoleInferenceResult("Mixdown", 0.55,
                                   f"Filename contains mixdown keyword '{weak}' and no instrument keyword.", weak)

    return RoleInferenceResult("Unknown", 0.2,
                               "No known role keyword matched the filename.", None)
