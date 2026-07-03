"""The built-in "Logic Indie Mix Evidence Demo" session.

To keep the repository light we generate short *synthetic* placeholder audio
files on demand (simple tones and filtered noise) rather than shipping real
recordings. These files are clearly labelled as synthetic examples: they exist
only to exercise the descriptor / graph / recommendation pipeline end-to-end.
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
    'Lead Vocal,Vocal,"Channel EQ; Compressor; DeEsser; Tape Delay",'
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
