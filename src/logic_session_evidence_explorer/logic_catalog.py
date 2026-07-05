"""Catalogue of Logic Pro's documented stock plug-ins and instruments.

Sourced from Apple's official guides ("Logic Pro Effects for Mac", 390 pp.,
and "Logic Pro Instruments for Mac", 752 pp.), enumerated from their tables of
contents, legacy chapters, and named mentions. Two uses:

1. **Channel-strip note enrichment.** A user note that names "Channel EQ" or
   "DeEsser 2" can be recognised as documented Logic stock processing and
   tagged with its category — third-party or unrecognised names simply stay
   untagged. The note remains a user assertion either way; recognition adds
   vocabulary, not trust.
2. **Role inference.** Logic names new tracks after the chosen patch or
   instrument ("When you choose a patch for a track, the track takes the name
   of the patch" — Logic Pro User Guide, p. 129), so exported stems routinely
   carry stock instrument names like "Alchemy" or "Ultrabeat". Distinctive
   instrument names therefore ground filename role inference in documented
   Logic vocabulary.

Category vocabulary for plug-ins: eq, dynamics, reverb, delay, modulation,
distortion, filter, imaging, pitch, utility, metering, amps_pedals,
multi_effects, specialized.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from .matching import tokenize

# --------------------------------------------------------------------------- #
# Stock audio effect plug-ins ("Logic Pro Effects for Mac", TOC pp. 2-6).
# --------------------------------------------------------------------------- #
STOCK_PLUGINS: dict[str, str] = {
    "Amp Designer": "amps_pedals",
    "Bass Amp Designer": "amps_pedals",
    "Pedalboard": "amps_pedals",
    "Delay Designer": "delay",
    "Echo": "delay",
    "Sample Delay": "delay",
    "Stereo Delay": "delay",
    "Tape Delay": "delay",
    "Bitcrusher": "distortion",
    "ChromaGlow": "distortion",
    "Clip Distortion": "distortion",
    "Distortion": "distortion",
    "Distortion II": "distortion",
    "Overdrive": "distortion",
    "Phase Distortion": "distortion",
    "Adaptive Limiter": "dynamics",
    "Compressor": "dynamics",
    "DeEsser 2": "dynamics",
    "Enveloper": "dynamics",
    "Expander": "dynamics",
    "Limiter": "dynamics",
    "Multipressor": "dynamics",
    "Noise Gate": "dynamics",
    "Surround Compressor": "dynamics",
    "Channel EQ": "eq",
    "Linear Phase EQ": "eq",
    "Match EQ": "eq",
    "Single Band EQ": "eq",
    "Vintage Console EQ": "eq",
    "Vintage Graphic EQ": "eq",
    "Vintage Tube EQ": "eq",
    "AutoFilter": "filter",
    "EVOC 20 Filterbank": "filter",
    "EVOC 20 TrackOscillator": "filter",
    "Fuzz-Wah": "filter",
    "Spectral Gate": "filter",
    "Binaural Post-Processing": "imaging",
    "Direction Mixer": "imaging",
    "Spatial Audio Monitoring": "imaging",
    "Stereo Spread": "imaging",
    "BPM Counter": "metering",
    "Correlation Meter": "metering",
    "Level Meter": "metering",
    "Loudness Meter": "metering",
    "MultiMeter": "metering",
    "Surround MultiMeter": "metering",
    "Tuner": "metering",
    "Chorus": "modulation",
    "Ensemble": "modulation",
    "Flanger": "modulation",
    "Microphaser": "modulation",
    "Modulation Delay": "modulation",
    "Phaser": "modulation",
    "Ringshifter": "modulation",
    "Rotor Cabinet": "modulation",
    "Scanner Vibrato": "modulation",
    "Spreader": "modulation",
    "Tremolo": "modulation",
    "Beat Breaker": "multi_effects",
    "Phat FX": "multi_effects",
    "Remix FX": "multi_effects",
    "Step FX": "multi_effects",
    "Pitch Correction": "pitch",
    "Pitch Shifter": "pitch",
    "Vocal Transformer": "pitch",
    "ChromaVerb": "reverb",
    "EnVerb": "reverb",
    "Quantec Room Simulator": "reverb",
    "SilverVerb": "reverb",
    "Space Designer": "reverb",
    "Exciter": "specialized",
    "Mastering Assistant": "specialized",
    "SubBass": "specialized",
    "Auto Sampler": "utility",
    "Down Mixer": "utility",
    "Gain": "utility",
    "I/O": "utility",
    "Multichannel Gain": "utility",
    "Test Oscillator": "utility",
}

# Legacy effects ("Logic Pro Effects for Mac", Legacy chapter pp. 365-388).
# "DeEsser" here is the predecessor of the current "DeEsser 2"; "Bass Amp" and
# "Guitar Amp Pro" precede Bass Amp Designer / Amp Designer.
LEGACY_PLUGINS: dict[str, str] = {
    "Bass Amp": "amps_pedals",
    "Guitar Amp Pro": "amps_pedals",
    "DeEsser": "dynamics",
    "Ducker": "dynamics",
    "Silver Compressor": "dynamics",
    "Silver Gate": "dynamics",
    "DJ EQ": "eq",
    "Fat EQ": "eq",
    "Silver EQ": "eq",
    "High Cut": "eq",
    "High Pass Filter": "eq",
    "High Shelving EQ": "eq",
    "Low Cut": "eq",
    "Low Pass Filter": "eq",
    "Low Shelving EQ": "eq",
    "Parametric EQ": "eq",
    "AVerb": "reverb",
    "GoldVerb": "reverb",
    "PlatinumVerb": "reverb",
    "Denoiser": "specialized",
    "Grooveshifter": "specialized",
    "Speech Enhancer": "specialized",
}

# --------------------------------------------------------------------------- #
# Stock software instruments ("Logic Pro Instruments for Mac", TOC pp. 2-8,
# legacy chapter pp. 710-721), mapped to this project's role taxonomy.
# Samplers and hosts that can play anything map to None (abstain), matching
# the evaluation's out-of-taxonomy policy. "Woodwind" also abstains: the
# taxonomy has no woodwind bucket.
# --------------------------------------------------------------------------- #
STOCK_INSTRUMENTS: dict[str, Optional[str]] = {
    "Alchemy": "Keys",
    "Drum Kit Designer": "Drums",
    "Drum Machine Designer": "Drums",
    "Drum Synth": "Drums",
    "Ultrabeat": "Drums",
    "ES1": "Keys",
    "ES2": "Keys",
    "EFM1": "Keys",
    "ES E": "Keys",
    "ES M": "Bass",  # explicitly bass-oriented per its chapter overview
    "ES P": "Keys",
    # Vocoder — arguably voice-derived, but "synth" in the name means the
    # Keys keyword always matches first; mapped Keys so the catalog agrees
    # with actual inference behaviour.
    "EVOC 20 PolySynth": "Keys",
    "Retro Synth": "Keys",
    "Sample Alchemy": None,
    "Sampler": None,
    "Quick Sampler": None,
    "Sculpture": "Keys",
    "Studio Bass": "Bass",
    "Studio Horns": "Brass",
    "Studio Piano": "Keys",
    "Studio Strings": "Strings",
    "Vintage B3": "Keys",
    "Vintage Clav": "Keys",
    "Vintage Electric Piano": "Keys",
    "Vintage Mellotron": "Keys",
    "External Instrument": None,
    "Klopfgeist": "FX",  # Logic's metronome click instrument
    # Legacy instruments (documented names, "Legacy" chapter):
    "Church Organ": "Keys",
    "Tonewheel Organ": "Keys",
    "Electric Clav": "Keys",
    "Tuned Percussion": "Drums",
    "Woodwind": None,
}


class PluginInfo(NamedTuple):
    name: str
    category: str
    generation: str  # "current" | "legacy"


def _token_index() -> dict[tuple, PluginInfo]:
    index: dict[tuple, PluginInfo] = {}
    for name, category in LEGACY_PLUGINS.items():
        index[tuple(tokenize(name))] = PluginInfo(name, category, "legacy")
    # Current entries win on collision.
    for name, category in STOCK_PLUGINS.items():
        index[tuple(tokenize(name))] = PluginInfo(name, category, "current")
    return index


_PLUGIN_INDEX = _token_index()

_INSTRUMENT_INDEX = {
    tuple(tokenize(name)): (name, role)
    for name, role in STOCK_INSTRUMENTS.items()
}


def lookup_plugin(name: str) -> Optional[PluginInfo]:
    """Recognise a documented Logic stock plug-in by (token-exact) name.

    Third-party or unrecognised names return ``None`` — that is expected, not
    an error; recognition only adds vocabulary to user-provided notes.
    """

    return _PLUGIN_INDEX.get(tuple(tokenize(name)))


def instrument_match(
    tokens: list[str],
) -> Optional[tuple[str, Optional[str], int, int]]:
    """Find the longest documented stock instrument name as a contiguous token
    subsequence and return ``(name, role_or_None, start_index, length)``.

    Matches ALL entries — including abstaining (``None``-role) ones — and keeps
    the longest, so "Sample Alchemy" (abstain) shadows the shorter "Alchemy"
    (Keys) it contains. Returns ``None`` when no instrument name matches at
    all. The ``start_index``/``length`` locate the matched name in ``tokens``,
    letting callers tell a keyword *inside* the instrument name ("Studio Horns"
    contains "horn") from one *outside* it ("Alchemy Bass").
    """

    best: Optional[tuple[str, Optional[str], int, int]] = None
    best_len = 0
    for key, (name, role) in _INSTRUMENT_INDEX.items():
        n = len(key)
        if n <= best_len:
            continue
        for i in range(len(tokens) - n + 1):
            if tuple(tokens[i:i + n]) == key:
                best = (name, role, i, n)
                best_len = n
                break
    return best


def instrument_role_in_tokens(tokens: list[str]) -> Optional[tuple[str, str]]:
    """Find a documented stock instrument name and return ``(name, role)``.

    Grounds role inference in Logic's documented behaviour of naming tracks
    after the chosen patch/instrument. Instruments mapped to ``None`` (e.g.
    Sampler) never produce a role — the correct behaviour there is abstention.
    """

    match = instrument_match(tokens)
    if match is not None and match[1] is not None:
        return (match[0], match[1])
    return None
