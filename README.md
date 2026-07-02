# Logic Session Evidence Explorer v0

*Interpretable DAW-state graphs from Logic Pro exports and partial session evidence.*

A research prototype exploring **Interpretable DAW-State Graphs for
Human-Centered AI-Assisted Music Production** — prepared in the context of a
preliminary PhD application to the Music Technology Group (MTG), Universitat
Pompeu Fabra, in collaboration with Steinberg.

## Research motivation

Music production concentrates structured knowledge inside a DAW's state: track
roles, plug-in chains, automation, routing, sends and buses. AI systems that aim
to *assist* rather than *replace* producers need to reason over this state in a
way a human can inspect and contest. But native project formats — Logic Pro's
`.logicx` among them — are proprietary and only *partially observable* through
what a workflow can export. This prototype treats that partial observability not
as a defect to hide, but as the phenomenon to model honestly.

## What this prototype does

- Ingests the evidence a Logic workflow can export: **stems / bounces, a stereo
  mixdown, MIDI, MusicXML**, plus optional **channel-strip notes**, a **session
  manifest**, and a **reference track**.
- Infers **track roles** from filenames, with confidence scores and
  explanations.
- Extracts **audio descriptors** (RMS, spectral centroid/bandwidth/rolloff,
  zero-crossing rate, onset strength, approximate tempo, optional LUFS).
- Builds an **interpretable, typed session graph** (NetworkX) that colour-codes
  every node by *observability*: observed / inferred / annotation / hidden /
  derived.
- Emits explicit **hidden-state markers** for Logic-native state that exports
  cannot reveal (plug-in chains, automation, routing).
- Produces **explainable, rule-based recommendations**, each with a confidence,
  explanation, suggested action and caveat.
- **Exports** everything to JSON (session evidence, graph, descriptors,
  recommendations, and a full research bundle).

## What this prototype does *not* do

> This prototype does not attempt full Logic Pro project reconstruction,
> proprietary `.logicx` parsing, or autonomous mixing. It demonstrates how
> exported DAW evidence can be represented, inspected, enriched, and used for
> explainable production assistance under partial observability.

Concretely, it never claims to recover plug-in chains, automation, sends, buses,
or track stacks from audio; it does not require Logic Pro, macOS, or any
heavyweight ML model; and it does not call heuristic recommendations "AI mixing".

## Why Logic Pro requires an evidence-based approach

Logic's project format is proprietary and effectively opaque to portable tools.
What is readily exportable — stems, a mixdown, MIDI, MusicXML — are *traces* of
the session, not the session itself. A stem tells us a filename, a duration, and
acoustic characteristics; it cannot tell us whether its sound was printed by a
plug-in chain or recorded that way. The explorer therefore models Logic as a
partially observable environment and makes the boundary between the observed and
the hidden a first-class feature. See [`docs/research_context.md`](docs/research_context.md).

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
# or, as an editable package (also installs the CLI entry point):
pip install -e .
```

## Usage

### Streamlit app

```bash
streamlit run src/logic_session_evidence_explorer/app.py
```

Then choose a mode in the sidebar:

1. **Built-in demo** — generates the synthetic *Logic Indie Mix Evidence Demo*
   and builds the full graph.
2. **Upload Logic exports** — upload stems, a mixdown, and a reference.
3. **Upload metadata** — add MIDI, MusicXML, channel-strip notes, and a manifest.
4. **About / limitations** — the observability legend and scope statement.

### Command line

```bash
python -m logic_session_evidence_explorer demo --out exports/demo
python -m logic_session_evidence_explorer scan-stems path/to/stems
python -m logic_session_evidence_explorer export-bundle path/to/stems --out bundle.json
```

Add `--no-descriptors` to skip audio analysis for a fast, filename-only pass.

## Input types

| Input | Required | Role |
| --- | --- | --- |
| Exported **stems** / bounces | at least stems *or* a mixdown | Primary observed audio evidence |
| Stereo **mixdown** | optional | Whole-mix evidence; enables reference comparison |
| **MIDI** file | optional | Track names, notes, tempo, time signatures |
| **MusicXML** file | optional | Score parts, keys, time signatures (notation, *not* mix state) |
| **Channel-strip notes** (CSV/JSON) | optional | User annotations: plug-ins, sends, buses |
| **Session manifest** (JSON) | optional | Role overrides and session metadata |
| **Reference track** | optional | A point of comparison for the mixdown |

See [`docs/logic_export_instructions.md`](docs/logic_export_instructions.md) for
how to produce these from Logic, and [`data/examples/`](data/examples) for
sample files.

## Graph schema overview

**Node types:** `session`, `audio_evidence`, `inferred_track`, `mixdown`,
`reference_track`, `midi_file`, `midi_track`, `musicxml_file`, `musicxml_part`,
`channel_strip_note`, `plugin_note`, `send_note`, `bus_note`, `descriptor_set`,
`hidden_state_marker`, `recommendation`.

**Edge types:** `contains_audio`, `infers_track`, `has_descriptor`,
`linked_to_midi`, `linked_to_score_part`, `annotated_by`, `mentions_plugin`,
`mentions_send`, `mentions_bus`, `compared_to_reference`, `has_hidden_state`,
`supports_recommendation`.

Every node carries an **observability** tag — `observed`, `inferred`,
`annotation`, `hidden`, or `derived` — and the graph metadata reports the
percentage of the graph that is observed vs inferred vs hidden.

## Recommendation examples

Rule-based and explainable. A few of the seven rules:

- **Add channel-strip notes** — stems present but no notes; the graph shows
  audio but not channel-strip state.
- **Vocal processing under-documented** — a vocal-like stem with no vocal-chain
  evidence.
- **Reference-aware evaluation could be added** — a mixdown with no reference.
- **Potential stem-level imbalance** — one stem far above the RMS median.
- **Printed processing may be present but undocumented** — low dynamic range on
  an undocumented stem.
- **Routing graph is probably incomplete** — many stems, no bus/send info.

Each recommendation includes a confidence, related nodes, an explanation, a
suggested action, and a caveat — and never asserts that a mix is "wrong".

## Hidden-state markers

For each class of Logic-native state exports cannot reveal, the graph emits an
explicit marker describing the hidden state, its consequence for reasoning, and
possible sources that could fill the gap:

- **Hidden plug-in chain** — printed processing is indistinguishable from raw
  recording in exported audio.
- **Hidden automation** — vocal rides, send throws and filter sweeps may be
  audible but are not editable DAW state.
- **Hidden routing** — buses, sends, track stacks and sidechains are not
  recoverable from stem audio alone.

## Audio descriptor extraction

Descriptors are computed with `librosa` (and optional `pyloudnorm` for true
LUFS). They characterise the *acoustic outcome* of a stem — not the processing
that produced it — and feed the transparent recommendation heuristics. Loudness
is reported in LUFS only when a proper loudness library is available; otherwise
it is left unset rather than approximated.

## Relationship to the PhD proposal

This is a small, honest proof of one idea a fuller PhD project would develop:
DAW state can be represented in an interpretable, human-centered way even when
the native format is proprietary or only partially observable. It demonstrates
evidence ingestion, typed graph construction, explicit uncertainty, and
explainable assistance — the properties an industrial partner (Steinberg) and a
research group (MTG) would need from a trustworthy AI-assisted production system.

## Limitations

- Role inference is filename keyword matching; it can be wrong and reports
  confidence accordingly.
- Descriptors describe audio, not DAW processing; they cannot confirm that any
  specific plug-in or setting was used.
- Channel-strip notes are *user assertions*, not extracted Logic state.
- MIDI/MusicXML/stem linking is heuristic name matching.
- AAF/ADM inspection is intentionally conservative (recorded as external
  interchange evidence, not fully parsed).

## Roadmap

- Stem-sum reconciliation against the mixdown when aligned exports are provided.
- Similarity comparison between two exported evidence bundles.
- Richer manifest-driven routing (explicit bus/send graph).
- Optional integration points for partner-provided session metadata.
- A session "fingerprint" summary and screenshot gallery.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
