"""The declarative observation model at the heart of the research framing.

The latent object of interest is the Logic session state S — track roles,
plug-in chains, parameter values, automation, sends, buses, track stacks. What
the explorer receives is a set of evidence artifacts E, and each artifact type
has an observation function O(artifact_type) describing which parts of S it
**reveals** (directly observable), **constrains** (supports inference with
stated confidence), **asserts** (user-provided claims, trusted as annotations
rather than observations), and **hides** (not recoverable from this artifact).

The hidden-state marker catalogue, the per-track hidden-field list, and the
annotation lift are *derived* from this table rather than hard-coded, making
the table the single thing to edit when a new evidence source (a second DAW,
partner metadata) moves the observability boundary. Session-level markers
(automation; routing, which folds in sends and track stacks) are deliberately
conservative: they remain even when individual tracks carry assertions,
because per-track notes do not establish session-wide routing.
"""

from __future__ import annotations

OBSERVATION_MODEL_VERSION = "0.1.0"

# The session-state fields this prototype reasons about. A fuller treatment
# would enumerate parameter-level state; field granularity is enough to make
# the observability boundary explicit.
SESSION_STATE_FIELDS = [
    "track_name",
    "role",
    "audio_content",
    "plugin_chain",
    "automation",
    "sends",
    "bus_routing",
    "track_stack",
]

# O(artifact_type): what each evidence artifact reveals / constrains / hides.
OBSERVATION_MODEL: dict[str, dict[str, list[str]]] = {
    "exported_audio": {
        "reveals": ["audio_content"],
        "constrains": ["track_name", "role"],
        "hides": ["plugin_chain", "automation", "sends", "bus_routing", "track_stack"],
    },
    "midi_export": {
        "reveals": ["track_name"],
        "constrains": ["role"],
        "hides": ["plugin_chain", "automation", "sends", "bus_routing", "track_stack"],
    },
    "musicxml_export": {
        "reveals": ["track_name"],
        "constrains": ["role"],
        "hides": ["plugin_chain", "automation", "sends", "bus_routing", "track_stack"],
    },
    "channel_strip_note": {
        # User assertions: treated as annotations, not observations.
        "asserts": ["role", "plugin_chain", "sends", "bus_routing"],
        "hides": ["automation", "track_stack"],
    },
    "session_manifest": {
        "asserts": ["role", "track_name"],
        "hides": ["plugin_chain", "automation", "sends", "bus_routing", "track_stack"],
    },
    "reference_track": {
        "reveals": ["audio_content"],
        "constrains": [],
        "hides": [],
    },
}

# Which channel-strip-note content lifts which hidden field from a track.
NOTE_FIELD_ASSERTIONS = {
    "plugins": "plugin_chain",
    "sends": "sends",
    "bus": "bus_routing",
}

# The hidden-state marker catalogue, derived from the fields no export
# reveals. ``target`` is "track" (one marker per undocumented track) or
# "session" (one marker for the whole session).
# Descriptions and consequences use Logic's documented constructs and
# terminology (Logic Pro User Guide: channel strips pp. 541-548, sends
# pp. 584-590, insert chain limit and serial order p. 583, track stacks
# pp. 161-167, VCA pp. 603-604, automation pp. 621-633, project
# alternatives pp. 105-109, mixer groups pp. 598-603).
HIDDEN_STATE_DEFINITIONS: dict[str, dict] = {
    "hidden_plugin_chain": {
        "target": "track",
        "field": "plugin_chain",
        "display_name": "Hidden plug-in chain",
        "description": (
            "Native Logic channel-strip state — the serial insert-effect chain "
            "(up to 15 Audio FX slots, processed top-down in insertion order) "
            "and its parameter values — is not directly observable from "
            "exported audio alone."
        ),
        "consequence": (
            "An exported stem carries only the summed acoustic result of the "
            "insert chain: recommendations based on stem audio and filename "
            "evidence cannot distinguish printed processing from raw recording, "
            "nor recover plug-in identity, order, or settings."
        ),
    },
    "hidden_automation": {
        "target": "session",
        "field": "automation",
        "display_name": "Hidden automation",
        "description": (
            "Automation state — Logic's track automation and region automation "
            "curves, their parameter targets, and per-track mode "
            "(Read/Touch/Latch/Write) — is not available from exported stems "
            "unless separately documented."
        ),
        "consequence": (
            "Temporal mix decisions such as vocal rides, send throws, or filter "
            "sweeps may be audible as a printed gain or timbre envelope, but the "
            "point-by-point curves and their targets are no longer editable "
            "DAW state."
        ),
    },
    "hidden_routing": {
        "target": "session",
        "field": "bus_routing",
        "display_name": "Hidden routing",
        "description": (
            "Routing state — sends (Pre Fader / Post Fader / Post Pan) to "
            "bus-fed aux channel strips, summing and folder track stacks, VCA "
            "group assignments, mixer groups, and sidechain sources — is not "
            "reliably recoverable from stem audio alone."
        ),
        "consequence": (
            "The graph may represent exported stems as flat tracks even if the "
            "original Logic session used subgroup buses, track stacks, or VCA "
            "faders. The structures themselves are unrecoverable: a mixer group "
            "links controls without touching signal flow, while a VCA fader or "
            "a folder stack's stack master (which functions as a VCA master "
            "fader) imprints gain into each stem indistinguishably from "
            "individual fader moves."
        ),
    },
}

# Evidence sources that could, in principle, fill each hidden-state gap.
POSSIBLE_SOURCES = [
    "user channel-strip notes",
    "screenshots",
    "manual export documentation",
    "future DAW integration",
    "partner-provided session metadata",
]

# Fields hidden on a track reconstructed from exported audio only.
TRACK_HIDDEN_FIELDS = list(OBSERVATION_MODEL["exported_audio"]["hides"])


def annotated_fields_from_note(note) -> list[str]:
    """Which state fields a channel-strip note asserts, given its content."""

    fields = []
    for attr, field in NOTE_FIELD_ASSERTIONS.items():
        if getattr(note, attr, None):
            fields.append(field)
    return fields


def hidden_fields_for_track(annotated_fields: list[str]) -> list[str]:
    """Track-level hidden fields, minus those the user has annotated."""

    return [f for f in TRACK_HIDDEN_FIELDS if f not in annotated_fields]


def session_level_definitions() -> list[tuple[str, dict]]:
    return [(k, v) for k, v in HIDDEN_STATE_DEFINITIONS.items() if v["target"] == "session"]


def track_level_definitions() -> list[tuple[str, dict]]:
    return [(k, v) for k, v in HIDDEN_STATE_DEFINITIONS.items() if v["target"] == "track"]
