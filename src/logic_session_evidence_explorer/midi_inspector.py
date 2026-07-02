"""MIDI inspection producing a :class:`MidiEvidence` summary.

Prefers ``mido`` (a pure-python dependency). Failures degrade to a warning so
that an unparseable MIDI file never aborts the session build.
"""

from __future__ import annotations

from typing import Optional

from . import utils
from .models import MidiEvidence

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _note_name(note_number: int) -> str:
    octave = note_number // 12 - 1
    return f"{_NOTE_NAMES[note_number % 12]}{octave}"


def inspect_midi(path: str, *, file_name: Optional[str] = None) -> MidiEvidence:
    file_name = file_name or utils.strip_extension(path)
    evidence = MidiEvidence(id=utils.make_id("midi"), file_name=file_name)

    try:
        import mido
    except Exception as exc:  # pragma: no cover - optional dependency
        evidence.warnings.append(f"mido not available; MIDI inspection skipped ({exc}).")
        return evidence

    try:
        mid = mido.MidiFile(path)
    except Exception as exc:
        evidence.warnings.append(f"Could not parse MIDI file ({exc}).")
        return evidence

    track_names: list[str] = []
    instrument_names: list[str] = []
    tempos: list[float] = []
    time_sigs: list[str] = []
    note_count = 0
    lowest: Optional[int] = None
    highest: Optional[int] = None

    for track in mid.tracks:
        for msg in track:
            if msg.type == "track_name":
                track_names.append(msg.name.strip())
            elif msg.type == "instrument_name":
                instrument_names.append(msg.name.strip())
            elif msg.type == "program_change":
                instrument_names.append(f"Program {msg.program}")
            elif msg.type == "set_tempo":
                bpm = round(mido.tempo2bpm(msg.tempo), 2)
                if bpm not in tempos:
                    tempos.append(bpm)
            elif msg.type == "time_signature":
                sig = f"{msg.numerator}/{msg.denominator}"
                if sig not in time_sigs:
                    time_sigs.append(sig)
            elif msg.type == "note_on" and msg.velocity > 0:
                note_count += 1
                lowest = msg.note if lowest is None else min(lowest, msg.note)
                highest = msg.note if highest is None else max(highest, msg.note)

    evidence.track_count = len(mid.tracks)
    evidence.note_count = note_count
    evidence.tempo_estimates = tempos
    evidence.time_signatures = time_sigs
    evidence.track_names = [n for n in track_names if n]
    evidence.instrument_names = list(dict.fromkeys(instrument_names))
    if lowest is not None and highest is not None:
        evidence.note_range = f"{_note_name(lowest)}–{_note_name(highest)}"
    return evidence
