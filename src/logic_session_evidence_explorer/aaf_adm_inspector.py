"""Conservative AAF / ADM interchange-file inspection.

Full AAF or ADM parsing is intentionally out of scope for this prototype. The
goal is to demonstrate *awareness* of professional interchange formats: we
record the file as external evidence, and — only when the file is obviously
XML-based ADM — pull a few high-level tags. Anything else returns a clear
"not implemented" warning rather than failing.
"""

from __future__ import annotations

import os
from xml.etree import ElementTree as ET

from . import utils

NOT_IMPLEMENTED_MESSAGE = (
    "AAF/ADM inspection is not implemented in this prototype; the file is "
    "recorded as external interchange evidence."
)


def inspect_interchange_file(path: str, *, file_name: str | None = None) -> dict:
    """Return a lightweight descriptor dict for an AAF / ADM-like file."""

    file_name = file_name or os.path.basename(path)
    ext = os.path.splitext(file_name.lower())[1].lstrip(".")
    result: dict = {
        "id": utils.make_id("interchange"),
        "file_name": file_name,
        "file_type": ext or "unknown",
        "size_bytes": None,
        "adm_tags": [],
        "warnings": [],
    }

    try:
        result["size_bytes"] = os.path.getsize(path)
    except OSError as exc:
        result["warnings"].append(f"Could not stat file ({exc}).")

    # Try a very light ADM-XML probe. ADM is XML-based; AAF is a binary
    # structured-storage format we do not attempt to read.
    if ext in {"xml", "adm"}:
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            tags = {child.tag.split("}")[-1] for child in root.iter()}
            adm_markers = {"frame", "coremetadata"}
            adm_like = sorted(
                t for t in tags
                if t.lower().startswith("audio") or t.lower() in adm_markers
            )
            if adm_like:
                result["adm_tags"] = adm_like[:20]
                result["warnings"].append(
                    "Detected ADM-like XML tags; only high-level tag names were recorded."
                )
            else:
                result["warnings"].append(
                    "XML file did not contain recognisable ADM tags."
                )
        except Exception as exc:
            result["warnings"].append(f"XML probe failed ({exc}). {NOT_IMPLEMENTED_MESSAGE}")
    else:
        result["warnings"].append(NOT_IMPLEMENTED_MESSAGE)

    return result
