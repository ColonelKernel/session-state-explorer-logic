"""The built-in synthetic demo sessions.

To keep the repository light we generate short *synthetic* placeholder audio
files on demand (simple tones and filtered noise) rather than shipping real
recordings. These files are clearly labelled as synthetic examples: they exist
only to exercise the descriptor / graph / recommendation pipeline end-to-end.

Two demos live here:

- :func:`build_demo_session` — the original small "Logic Indie Mix Evidence
  Demo" (stems + notes CSV only). Kept exactly as-is; tests depend on it.
- :func:`build_full_demo` — the "Logic Full Evidence Demo", which exercises
  the FULL evidence pipeline: eight role-diverse stems, a mixdown that is the
  exact scaled sum of the stems (so stem-sum reconciliation finds a low
  residual and recovers the known gain), a spectrally different reference
  track, a Standard MIDI File and a MusicXML score whose part names token-match
  stems, and a channel-strip notes CSV with sends/buses and one non-stock
  plug-in. Everything stays synthetic and is labelled as such.
"""

from __future__ import annotations

import math
import os
import struct
import tempfile
import wave

from . import session_builder, stem_scanner, utils
from .models import ChannelStripNote, SessionEvidence

DEMO_SESSION_NAME = "Logic Indie Mix Evidence Demo"

# (filename, kind, base_frequency_hz) — kind selects the synthetic generator.
DEMO_STEMS = [
    ("01_Drums_Bounce.wav", "noise_burst", 0.0),
    ("02_Bass_Bounce.wav", "tone", 55.0),
    ("03_Electric_Guitar_Bounce.wav", "tone", 220.0),
    ("04_Synth_Pad_Bounce.wav", "pad", 330.0),
    ("05_Lead_Vocal_Bounce.wav", "tone", 440.0),
    ("06_Backing_Vocals_Bounce.wav", "tone", 550.0),
    ("Stereo_Mix_Bounce.wav", "mix", 0.0),
]

DEMO_NOTES_CSV = (
    "track_name,role,plugins,sends,bus,notes\n"
    'Lead Vocal,Vocal,"Channel EQ; Compressor; DeEsser 2; Tape Delay",'
    '"Vocal Verb; Slap Delay","Vocal Bus","Main lead vocal chain (synthetic demo)"\n'
    'Drums,Drums,"Channel EQ; Compressor; Saturation","Room Verb","Drum Bus",'
    '"Printed drum stem (synthetic demo)"\n'
)


def _write_synth_wav(path: str, kind: str, freq: float, *, seconds: float = 2.0, sr: int = 22050) -> None:
    """Write a short mono 16-bit WAV using only the stdlib (no numpy needed)."""

    n = int(seconds * sr)
    # Deterministic pseudo-noise so demo descriptors are reproducible.
    state = 12345

    def rnd() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return (state / 0x7FFFFFFF) * 2.0 - 1.0

    samples = []
    for i in range(n):
        t = i / sr
        env = min(1.0, t * 8) * max(0.0, 1.0 - (t / seconds) ** 2)
        # Sustained envelope (attack, then hold) — models a low-crest, "printed"
        # sounding signal such as a compressed pad.
        sustain_env = min(1.0, t * 8)
        if kind == "tone":
            s = 0.5 * math.sin(2 * math.pi * freq * t) * env
        elif kind == "pad":
            s = (
                0.55 * math.sin(2 * math.pi * freq * t)
                + 0.4 * math.sin(2 * math.pi * freq * 1.5 * t)
            ) * sustain_env
        elif kind == "noise_burst":
            beat = 1.0 if (i % (sr // 2)) < (sr // 20) else 0.15
            s = 0.6 * rnd() * beat
        elif kind == "mix":
            s = (
                0.25 * math.sin(2 * math.pi * 110 * t)
                + 0.2 * math.sin(2 * math.pi * 440 * t)
                + 0.15 * rnd()
            ) * env
        else:
            s = 0.3 * math.sin(2 * math.pi * 440 * t) * env
        samples.append(max(-1.0, min(1.0, s)))

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = b"".join(struct.pack("<h", int(s * 32767)) for s in samples)
        wf.writeframes(frames)


def generate_demo_audio(target_dir: str | None = None) -> str:
    """Generate the synthetic demo WAVs in ``target_dir`` (a temp dir by default).

    Returns the directory containing the files. Existing files are reused.
    """

    target_dir = target_dir or os.path.join(
        tempfile.gettempdir(), "logic_session_evidence_demo"
    )
    os.makedirs(target_dir, exist_ok=True)
    for file_name, kind, freq in DEMO_STEMS:
        path = os.path.join(target_dir, file_name)
        if not os.path.exists(path):
            _write_synth_wav(path, kind, freq)
    return target_dir


def build_demo_session(*, with_descriptors: bool = True, target_dir: str | None = None) -> SessionEvidence:
    """Build and fully assemble the demo :class:`SessionEvidence`."""

    utils.reset_ids()
    folder = generate_demo_audio(target_dir)

    paths = [os.path.join(folder, name) for name, _k, _f in DEMO_STEMS]
    audio_files = stem_scanner.scan_paths(paths)

    from .manifest_loader import load_channel_strip_notes_csv

    notes, _warnings = load_channel_strip_notes_csv(DEMO_NOTES_CSV)

    session = SessionEvidence(
        session_name=DEMO_SESSION_NAME,
        daw_name="Logic Pro",
        daw_version="11",
        source_type="synthetic_demo",
        audio_files=audio_files,
        channel_strip_notes=notes,
        warnings=[
            "Demo audio is synthetic (generated tones/noise), not a real Logic export.",
        ],
        metadata={"synthetic": True, "audio_dir": folder},
    )
    return session_builder.finalize_session(session, with_descriptors=with_descriptors)


# =========================================================================== #
# The "Logic Full Evidence Demo": every evidence kind the pipeline accepts.
# =========================================================================== #

FULL_DEMO_SESSION_NAME = "Logic Full Evidence Demo"

FULL_DEMO_SAMPLE_RATE = 22050
FULL_DEMO_SECONDS = 3.0

# The mixdown is written as exactly ``FULL_DEMO_MIX_GAIN * sum(stem samples)``
# (summed in the integer sample domain, then re-quantised once), so stem-sum
# reconciliation should recover this gain with a residual at the 16-bit
# quantisation floor. The per-stem peak amplitudes below sum to ~1.7, keeping
# the scaled mix safely below full scale.
FULL_DEMO_MIX_GAIN = 0.5

# (filename, kind, base_frequency_hz, peak_amplitude) — filenames deliberately
# use realistic Logic decorations ("_bip" bounce-in-place suffix, numbered
# exports, plain instrument names) to exercise role inference and track-index
# parsing. Distinct generators/amplitudes give each stem a distinct RMS and
# spectrum so descriptors differ per stem.
FULL_DEMO_STEMS = [
    ("01 Lead Vocal_bip.wav", "vocal", 440.0, 0.32),
    ("02 BGV Stack.wav", "pad", 550.0, 0.16),
    ("Kick.wav", "kick", 60.0, 0.30),
    ("Snare Top.wav", "snare", 0.0, 0.22),
    ("Bass DI.wav", "bass", 55.0, 0.28),
    ("Piano.wav", "piano", 261.63, 0.20),
    ("Violins Section.wav", "strings", 660.0, 0.12),
    ("FX Riser.wav", "riser", 200.0, 0.10),
]

FULL_DEMO_MIXDOWN_NAME = "Stereo Mix.wav"          # strong mixdown keyword
FULL_DEMO_REFERENCE_NAME = "Reference - Neon Skyline.wav"  # reference keyword
FULL_DEMO_MIDI_NAME = "Logic Full Evidence Demo.mid"
FULL_DEMO_MUSICXML_NAME = "Logic Full Evidence Demo Score.musicxml"
FULL_DEMO_NOTES_NAME = "channel strip notes.csv"
FULL_DEMO_MANIFEST_NAME = "session manifest.json"

# Names shared between the MIDI file / MusicXML score and the stems, so token
# matching links them to the inferred tracks.
FULL_DEMO_MIDI_TRACKS = ["Bass DI", "Piano", "Violins Section"]
FULL_DEMO_MUSICXML_PARTS = ["Lead Vocal", "Piano", "Violins Section"]

# Richer channel-strip notes: a vocal chain with a send and bus, a drum-bus
# note (deliberately matching no single stem — bus-level documentation), and a
# piano chain including "Warmify Pro", a plug-in NOT in the stock catalogue
# (exercises the unknown-family path).
FULL_DEMO_NOTES_CSV = (
    "track_name,role,plugins,sends,bus,notes\n"
    'Lead Vocal,Vocal,"Channel EQ; Compressor; DeEsser 2","Reverb","Bus 1",'
    '"Lead vocal chain: subtractive EQ into gentle compression, then de-essing '
    '(synthetic demo)"\n'
    'Drum Bus,Drums,,,"Bus 2",'
    '"Kick and Snare Top are summed to a drum bus in the original session '
    '(synthetic demo)"\n'
    'Piano,Keys,"Compressor; Space Designer; Warmify Pro",,"Inst 3",'
    '"Piano chain; Warmify Pro is a third-party plug-in outside the stock '
    'catalogue (synthetic demo)"\n'
)

FULL_DEMO_MANIFEST_JSON = (
    "{\n"
    '  "schema_version": "0.1.0",\n'
    f'  "session_name": "{FULL_DEMO_SESSION_NAME}",\n'
    '  "daw_name": "Logic Pro",\n'
    '  "daw_version": "11",\n'
    '  "source_type": "synthetic_demo",\n'
    '  "notes": "Synthetic full-evidence demo: every file generated by '
    'logic_session_evidence_explorer.demo.generate_full_demo_files()."\n'
    "}\n"
)


def _lcg(seed: int):
    """Deterministic pseudo-noise source in [-1, 1] (same LCG as the demo)."""

    state = seed & 0x7FFFFFFF

    def rnd() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return (state / 0x7FFFFFFF) * 2.0 - 1.0

    return rnd


def _full_demo_stem_ints(kind: str, freq: float, amp: float, *, seed: int,
                         sr: int = FULL_DEMO_SAMPLE_RATE,
                         seconds: float = FULL_DEMO_SECONDS) -> list[int]:
    """One stem as 16-bit integer samples. Each ``kind`` has a musically
    distinct synthetic character (different spectrum, envelope and RMS)."""

    rnd = _lcg(seed)
    n = int(seconds * sr)
    two_pi = 2 * math.pi
    out: list[int] = []
    for i in range(n):
        t = i / sr
        if kind == "vocal":
            vibrato = 1.0 + 0.012 * math.sin(two_pi * 5.5 * t)
            env = min(1.0, t * 6) * (0.55 + 0.45 * math.sin(two_pi * 0.5 * t) ** 2)
            s = math.sin(two_pi * freq * vibrato * t) * env
        elif kind == "pad":
            env = min(1.0, t * 3)
            s = (0.6 * math.sin(two_pi * freq * t)
                 + 0.4 * math.sin(two_pi * freq * 1.25 * t)) * env
        elif kind == "kick":
            pos = (i % (sr // 2)) / sr  # two hits per second
            s = math.sin(two_pi * freq * pos) * math.exp(-pos * 18.0)
        elif kind == "snare":
            pos = ((i + sr // 4) % (sr // 2)) / sr  # off-beat noise bursts
            s = rnd() * math.exp(-pos * 25.0)
        elif kind == "bass":
            gate = 1.0 if (i % (sr // 2)) < (3 * sr // 8) else 0.0
            s = (0.8 * math.sin(two_pi * freq * t)
                 + 0.2 * math.sin(two_pi * freq * 3 * t)) * gate
        elif kind == "piano":
            pos = (i % sr) / sr  # one decaying chord per second
            s = (math.sin(two_pi * freq * t)
                 + 0.5 * math.sin(two_pi * freq * 2 * t)
                 + 0.25 * math.sin(two_pi * freq * 3 * t)) * math.exp(-pos * 3.0) / 1.75
        elif kind == "strings":
            env = min(1.0, t * 2)
            s = (math.sin(two_pi * freq * t)
                 + math.sin(two_pi * freq * 1.5 * t)
                 + math.sin(two_pi * freq * 2 * t)) * env / 3.0
        elif kind == "riser":
            ramp = (t / seconds) ** 1.5
            sweep = math.sin(two_pi * freq * (1.0 + t / seconds) * t)
            s = (0.7 * rnd() + 0.3 * sweep) * ramp
        elif kind == "reference":
            # Spectrally different from the mix: bright noise bed + a triad in
            # another key with its own rhythm.
            env = 0.6 + 0.4 * math.sin(two_pi * 1.5 * t) ** 2
            s = (0.45 * rnd()
                 + 0.30 * math.sin(two_pi * 330.0 * t)
                 + 0.15 * math.sin(two_pi * 990.0 * t)
                 + 0.10 * math.sin(two_pi * 1980.0 * t)) * env
        else:
            s = math.sin(two_pi * 440.0 * t)
        s = max(-1.0, min(1.0, s * amp))
        out.append(int(round(s * 32767)))
    return out


def _write_wav_ints(path: str, ints: list[int], *, sr: int = FULL_DEMO_SAMPLE_RATE) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"".join(struct.pack("<h", v) for v in ints))


# --------------------------------------------------------------------------- #
# Standard MIDI File, hand-built from bytes (stdlib only, no mido required)
# --------------------------------------------------------------------------- #
def _midi_varlen(value: int) -> bytes:
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def _midi_meta(delta: int, meta_type: int, payload: bytes) -> bytes:
    return _midi_varlen(delta) + bytes([0xFF, meta_type, len(payload)]) + payload


def _midi_note(delta: int, pitch: int, duration: int, velocity: int = 96) -> bytes:
    return (_midi_varlen(delta) + bytes([0x90, pitch, velocity])
            + _midi_varlen(duration) + bytes([0x80, pitch, 0]))


def _midi_track(body: bytes) -> bytes:
    body += _midi_meta(0, 0x2F, b"")  # end of track
    return b"MTrk" + struct.pack(">I", len(body)) + body


def build_full_demo_midi_bytes() -> bytes:
    """A tiny format-1 SMF: tempo track + three named tracks matching stems."""

    ppq = 480
    header = b"MThd" + struct.pack(">IHHH", 6, 1, 1 + len(FULL_DEMO_MIDI_TRACKS), ppq)
    conductor = _midi_track(
        _midi_meta(0, 0x03, FULL_DEMO_SESSION_NAME.encode("ascii"))
        + _midi_meta(0, 0x51, (500_000).to_bytes(3, "big"))       # 120 bpm
        + _midi_meta(0, 0x58, bytes([4, 2, 24, 8]))               # 4/4
    )
    pitch_lines = {
        "Bass DI": [28, 31, 33, 28],            # E1 G1 A1 E1
        "Piano": [60, 64, 67, 72],              # C4 E4 G4 C5
        "Violins Section": [69, 74, 81],        # A4 D5 A5
    }
    tracks = b""
    for name in FULL_DEMO_MIDI_TRACKS:
        body = _midi_meta(0, 0x03, name.encode("ascii"))
        for pitch in pitch_lines[name]:
            body += _midi_note(0, pitch, ppq)
        tracks += _midi_track(body)
    return header + conductor + tracks


# --------------------------------------------------------------------------- #
# Minimal hand-written MusicXML score (parses with music21 or plain etree)
# --------------------------------------------------------------------------- #
def build_full_demo_musicxml() -> str:
    part_list = "".join(
        f'    <score-part id="P{i + 1}"><part-name>{name}</part-name></score-part>\n'
        for i, name in enumerate(FULL_DEMO_MUSICXML_PARTS)
    )
    notes = {
        "Lead Vocal": ("A", 4),
        "Piano": ("C", 4),
        "Violins Section": ("A", 5),
    }
    parts = ""
    for i, name in enumerate(FULL_DEMO_MUSICXML_PARTS):
        step, octave = notes[name]
        parts += (
            f'  <part id="P{i + 1}">\n'
            "    <measure number=\"1\">\n"
            "      <attributes>\n"
            "        <divisions>1</divisions>\n"
            "        <key><fifths>2</fifths></key>\n"
            "        <time><beats>4</beats><beat-type>4</beat-type></time>\n"
            "        <clef><sign>G</sign><line>2</line></clef>\n"
            "      </attributes>\n"
            f"      <note><pitch><step>{step}</step><octave>{octave}</octave></pitch>"
            "<duration>4</duration><type>whole</type></note>\n"
            "    </measure>\n"
            "    <measure number=\"2\">\n"
            f"      <note><pitch><step>{step}</step><octave>{octave}</octave></pitch>"
            "<duration>4</duration><type>whole</type></note>\n"
            "    </measure>\n"
            "  </part>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<score-partwise version="3.1">\n'
        f"  <work><work-title>{FULL_DEMO_SESSION_NAME}</work-title></work>\n"
        "  <part-list>\n"
        f"{part_list}"
        "  </part-list>\n"
        f"{parts}"
        "</score-partwise>\n"
    )


def generate_full_demo_files(target_dir: str | None = None) -> str:
    """Generate every full-demo evidence file in ``target_dir``.

    Writes the eight stems, the mixdown (exact scaled stem sum), the reference
    track, the MIDI file, the MusicXML score, the channel-strip notes CSV and
    the session manifest. Existing files are reused, mirroring
    :func:`generate_demo_audio`. Returns the directory.
    """

    target_dir = target_dir or os.path.join(
        tempfile.gettempdir(), "logic_session_evidence_full_demo"
    )
    os.makedirs(target_dir, exist_ok=True)

    mix_path = os.path.join(target_dir, FULL_DEMO_MIXDOWN_NAME)
    stems_missing = [
        (name, kind, freq, amp)
        for name, kind, freq, amp in FULL_DEMO_STEMS
        if not os.path.exists(os.path.join(target_dir, name))
    ]
    if stems_missing or not os.path.exists(mix_path):
        # (Re)build stems and mixdown together so the mix is always the exact
        # scaled sum of the stems on disk.
        stem_ints: list[list[int]] = []
        for index, (name, kind, freq, amp) in enumerate(FULL_DEMO_STEMS):
            ints = _full_demo_stem_ints(kind, freq, amp, seed=12345 + index * 991)
            _write_wav_ints(os.path.join(target_dir, name), ints)
            stem_ints.append(ints)
        mix_ints = [
            max(-32768, min(32767, int(round(FULL_DEMO_MIX_GAIN * sum(column)))))
            for column in zip(*stem_ints)
        ]
        _write_wav_ints(mix_path, mix_ints)

    ref_path = os.path.join(target_dir, FULL_DEMO_REFERENCE_NAME)
    if not os.path.exists(ref_path):
        _write_wav_ints(ref_path, _full_demo_stem_ints("reference", 330.0, 0.5, seed=777))

    text_files = {
        FULL_DEMO_MIDI_NAME: build_full_demo_midi_bytes(),
        FULL_DEMO_MUSICXML_NAME: build_full_demo_musicxml().encode("utf-8"),
        FULL_DEMO_NOTES_NAME: FULL_DEMO_NOTES_CSV.encode("utf-8"),
        FULL_DEMO_MANIFEST_NAME: FULL_DEMO_MANIFEST_JSON.encode("utf-8"),
    }
    for name, payload in text_files.items():
        path = os.path.join(target_dir, name)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(payload)
    return target_dir


def build_full_demo(*, with_descriptors: bool = True, target_dir: str | None = None) -> SessionEvidence:
    """Build the "Logic Full Evidence Demo": every evidence kind at once.

    With descriptors enabled (the default; librosa required for the signal
    comparisons, with the same graceful degradation as everywhere else) the
    finalized session carries MIDI evidence, MusicXML evidence, channel-strip
    notes, per-file descriptors, a stem-sum reconciliation with a low residual
    and a fitted gain of ~``FULL_DEMO_MIX_GAIN``, and a reference comparison.
    """

    utils.reset_ids()
    folder = generate_full_demo_files(target_dir)

    from . import midi_inspector, musicxml_inspector
    from .manifest_loader import load_channel_strip_notes_csv

    names = [name for name, _kind, _freq, _amp in FULL_DEMO_STEMS]
    names += [FULL_DEMO_MIXDOWN_NAME, FULL_DEMO_REFERENCE_NAME]
    audio_files = stem_scanner.scan_paths([os.path.join(folder, n) for n in names])

    notes, note_warnings = load_channel_strip_notes_csv(FULL_DEMO_NOTES_CSV)
    midi_evidence = midi_inspector.inspect_midi(
        os.path.join(folder, FULL_DEMO_MIDI_NAME), file_name=FULL_DEMO_MIDI_NAME
    )
    musicxml_evidence = musicxml_inspector.inspect_musicxml(
        os.path.join(folder, FULL_DEMO_MUSICXML_NAME), file_name=FULL_DEMO_MUSICXML_NAME
    )

    session = SessionEvidence(
        session_name=FULL_DEMO_SESSION_NAME,
        daw_name="Logic Pro",
        daw_version="11",
        source_type="synthetic_demo",
        audio_files=audio_files,
        midi_evidence=midi_evidence,
        musicxml_evidence=musicxml_evidence,
        channel_strip_notes=notes,
        warnings=[
            "Demo audio is synthetic (generated tones/noise), not a real Logic export.",
            "Full-evidence demo: the mixdown is the exact scaled sum of the "
            f"stems (gain {FULL_DEMO_MIX_GAIN}), so a low stem-sum residual is "
            "expected by construction.",
            *note_warnings,
        ],
        metadata={
            "synthetic": True,
            "audio_dir": folder,
            "mix_gain": FULL_DEMO_MIX_GAIN,
        },
    )
    return session_builder.finalize_session(session, with_descriptors=with_descriptors)
