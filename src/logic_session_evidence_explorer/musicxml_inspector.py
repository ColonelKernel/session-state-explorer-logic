"""MusicXML inspection producing a :class:`MusicXmlEvidence` summary.

Uses ``music21`` when available for richer key/measure detection, and falls
back to plain ``xml.etree`` parsing (which handles both raw ``.musicxml`` and
compressed ``.mxl`` containers) so the feature works without heavy deps.

Note: MusicXML describes *score / notation* evidence, not mix state. Callers
should surface that distinction in the UI.
"""

from __future__ import annotations

import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

from . import utils
from .models import MusicXmlEvidence


def _read_musicxml_bytes(path: str) -> bytes:
    """Return raw MusicXML bytes, transparently unzipping ``.mxl`` files."""

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            # A compressed MusicXML container points at the root score via
            # META-INF/container.xml; fall back to the first .xml member.
            names = zf.namelist()
            score_name = None
            if "META-INF/container.xml" in names:
                try:
                    container = ET.fromstring(zf.read("META-INF/container.xml"))
                    rootfile = container.find(".//{*}rootfile")
                    if rootfile is not None:
                        score_name = rootfile.get("full-path")
                except Exception:
                    score_name = None
            if not score_name:
                score_name = next(
                    (n for n in names if n.lower().endswith((".xml", ".musicxml"))),
                    None,
                )
            if score_name:
                return zf.read(score_name)
    with open(path, "rb") as fh:
        return fh.read()


def _inspect_with_etree(path: str, evidence: MusicXmlEvidence) -> MusicXmlEvidence:
    try:
        raw = _read_musicxml_bytes(path)
        root = ET.fromstring(raw)
    except Exception as exc:
        evidence.warnings.append(f"Could not parse MusicXML ({exc}).")
        return evidence

    # ``{*}`` wildcards ignore the MusicXML namespace if present.
    part_names = [
        (pn.text or "").strip()
        for pn in root.findall(".//{*}part-list//{*}part-name")
        if (pn.text or "").strip()
    ]
    parts = root.findall(".//{*}part")
    measures = root.findall(".//{*}part/{*}measure")

    time_sigs = []
    for time in root.findall(".//{*}time"):
        beats = time.findtext("{*}beats")
        beat_type = time.findtext("{*}beat-type")
        if beats and beat_type:
            sig = f"{beats}/{beat_type}"
            if sig not in time_sigs:
                time_sigs.append(sig)

    keys = []
    for key in root.findall(".//{*}key"):
        fifths = key.findtext("{*}fifths")
        if fifths is not None and fifths not in keys:
            keys.append(f"{fifths} fifths")

    evidence.part_names = part_names
    evidence.part_count = len(parts) or (len(part_names) or None)
    evidence.measure_count = len(measures) or None
    evidence.detected_time_signatures = time_sigs
    evidence.detected_keys = keys
    evidence.warnings.append(
        "Parsed with basic XML fallback; key names are given as fifths counts."
    )
    return evidence


def inspect_musicxml(path: str, *, file_name: Optional[str] = None) -> MusicXmlEvidence:
    file_name = file_name or utils.strip_extension(path)
    evidence = MusicXmlEvidence(id=utils.make_id("musicxml"), file_name=file_name)

    try:
        from music21 import converter
    except Exception:
        return _inspect_with_etree(path, evidence)

    try:
        score = converter.parse(path)
    except Exception as exc:
        evidence.warnings.append(
            f"music21 could not parse the file, falling back to XML ({exc})."
        )
        return _inspect_with_etree(path, evidence)

    try:
        parts = list(score.parts)
        evidence.part_count = len(parts)
        evidence.part_names = [
            (p.partName or f"Part {i + 1}").strip() for i, p in enumerate(parts)
        ]
        measures = score.recurse().getElementsByClass("Measure")
        evidence.measure_count = len(measures) or None

        time_sigs = {
            ts.ratioString for ts in score.recurse().getElementsByClass("TimeSignature")
        }
        evidence.detected_time_signatures = sorted(time_sigs)

        keys = set()
        for k in score.recurse().getElementsByClass("KeySignature"):
            try:
                keys.add(k.asKey().name)
            except Exception:
                keys.add(str(k))
        evidence.detected_keys = sorted(keys)
    except Exception as exc:
        evidence.warnings.append(f"music21 summary partially failed ({exc}).")

    return evidence
