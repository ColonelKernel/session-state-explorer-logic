# Repository audit (Phase 0)

An honest account of what the *Logic Session Evidence Explorer* actually is,
before the cross-DAW canonical layer is added. Written to satisfy the
"understand before you change" principle: the cross-DAW work builds **above**
this, and must not break it.

> **Framing correction.** The cross-DAW directive uses live-"extraction"
> language. This repository is **not** a live Logic-state extractor. It is an
> *evidence-based* explorer whose entire research thesis is **partial
> observability**: it works from what a Logic workflow can *export*, and it
> never parses the proprietary `.logicx` project. That is a feature, not a gap —
> the observed/inferred/annotated/hidden distinctions the directive asks for are
> already first-class here.

## A. Current product

- **What it does:** ingests exported Logic artifacts and builds an interpretable
  DAW-state *evidence graph* — inferring track roles, extracting audio
  descriptors, running signal-level analyses, emitting explicit hidden-state
  markers, producing explainable recommendations, and exporting JSON (including
  a PROV-O provenance view).
- **Launch:** `streamlit run src/logic_session_evidence_explorer/app.py`, or the
  CLI `python -m logic_session_evidence_explorer {demo,scan-stems,export-bundle}`.
- **Input:** exported stems/bounces, a stereo mixdown, a reference track, MIDI,
  MusicXML, channel-strip notes (CSV/JSON), a session manifest, and an AAF/ADM
  interchange file (recorded, not parsed).
- **Output:** an interactive graph, tables, recommendation cards, and JSON
  exports (`session_evidence`, `graph`, `descriptors`, `recommendations`,
  `full_bundle`, `prov_json`).
- **Happy path:** *Built-in demo → Build demo session →* summary with an
  observability meter → layered graph → recommendations with evidence
  highlighting → JSON export. The demo (no descriptors) yields **7 audio files,
  6 inferred tracks, 6 hidden-state markers, 36 graph nodes / 35 edges**.

## B. Current state acquisition (the "acquisition layer")

All acquisition is **offline, from exported artifacts** — deterministic,
cross-platform, no macOS APIs, no Logic install required.

| Source | Mechanism | Entry point | Live/offline | Deterministic | Stability |
| --- | --- | --- | --- | --- | --- |
| Stems / mixdown / reference | filename scan + `soundfile` header | `stem_scanner.py` | offline | yes | reliable |
| Audio descriptors | `librosa` (+ optional `pyloudnorm`) | `audio_descriptors.py` | offline | mostly (lib-version sensitive) | reliable |
| Stem-sum / reference comparison | FFT/RMS DSP | `signal_comparisons.py` | offline | yes | reliable |
| MIDI | `mido` | `midi_inspector.py` | offline | yes | reliable |
| MusicXML | `music21` + `etree` fallback | `musicxml_inspector.py` | offline | yes | reliable |
| Channel-strip notes / manifest | CSV/JSON parse | `manifest_loader.py` | offline | yes | reliable (user-asserted) |
| AAF/ADM | recorded only, not parsed | `aaf_adm_inspector.py` | offline | yes | stub by design |

There is **no** live capture: no `.logicx` parsing, no Accessibility API, no
control surface, no subprocess into Logic. (The cross-DAW program adds these as
*new, gated* capture methods — it does not replace the above.)

## C. Existing state model

Typed models in [models.py](../src/logic_session_evidence_explorer/models.py):
`SessionEvidence` (root) · `AudioEvidence` · `MidiEvidence` ·
`MusicXmlEvidence` · `ChannelStripNote` · `ReferenceTrackEvidence` ·
`InferredTrackState` · `HiddenStateMarker` · `AudioDescriptorSet` ·
`StemSumReconciliation` · `ReferenceComparison` · `Recommendation` ·
`GraphExport`. This `SessionEvidence` **is** the native Logic model — it becomes
the *NativeLogicSnapshot* of the adapter architecture, preserved intact.

The graph ([graph_builder.py](../src/logic_session_evidence_explorer/graph_builder.py))
already tags every node with an **observability class** — `observed`,
`inferred`, `annotation`, `hidden`, `derived` — and reports observed/inferred/
hidden **percentages** in graph metadata. Node types: `session`,
`audio_evidence`, `inferred_track`, `mixdown`, `reference_track`, `midi_file/
track`, `musicxml_file/part`, `channel_strip_note`, `plugin_note`, `send_note`,
`bus_note`, `descriptor_set`, `stem_sum_reconciliation`, `reference_comparison`,
`hidden_state_marker`, `recommendation`.

## D. Existing UI

Streamlit ([app.py](../src/logic_session_evidence_explorer/app.py)): sidebar
**modes** (Built-in demo · Upload Logic exports · Upload metadata · About) and,
after a build, **tabs** (Graph · Tables · Recommendations · Export). Notable:
the observability *evidence meter*, the layered-by-observability PyVis graph
with evidence highlighting, and provenance-aware exports. Theme in
`.streamlit/config.toml`.

## E. Technical debt and risk

- **Module-global id counters** (`utils._ID_COUNTERS`, reset via `reset_ids()`)
  — deterministic per build but shared process-wide; every entry point resets.
  Fine for single-session use; a concern the canonical layer must not inherit
  (it should derive stable ids, not reuse these globally).
- **Descriptor determinism** is library-version sensitive (`librosa`,
  `pyloudnorm`); the golden baseline therefore freezes the **no-descriptors**
  bundle only.
- **Acquisition ↔ graph coupling** is moderate: `graph_builder` reads
  `SessionEvidence` directly. The canonical normalizer will sit alongside it,
  reading the same model — not through the graph.
- **No live/native capture** — intentional, but the directive wants it added;
  it must be additive and gated (see plan).

## F. Reusable assets

- **KEEP AS IS:** `models.py`, `stem_scanner`, `role_inference`, `logic_catalog`,
  `matching`, `audio_descriptors`, `signal_comparisons`, `midi/musicxml/aaf`
  inspectors, `manifest_loader`, `recommendations`, `session_builder`, `demo`,
  `eval/`. These are the Logic adapter's **evidence** capture method.
- **KEEP BUT WRAP:** `graph_builder` (observability tags feed canonical
  evidence), `observation_model` (feeds the capability manifest), `export`
  (`prov_json` is the provenance backbone), `visualization` (reused by the
  Compare view).
- **REFACTOR (additive):** `app.py` / `cli.py` gain a Compare mode / canonical
  commands — existing modes untouched.
- **REPLACE LATER:** nothing yet.
- **DELETE ONLY AFTER MIGRATION:** nothing.

Net: the canonical cross-DAW layer is **purely additive**. No existing subsystem
is removed or rewritten.
