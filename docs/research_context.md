# Research context

*Interpretable DAW-State Graphs for Human-Centered AI-Assisted Music Production*
— a preliminary prototype prepared in the context of a PhD application to the
Music Technology Group (MTG), Universitat Pompeu Fabra, in collaboration with
Steinberg.

## DAW-state representation

Modern music production concentrates a large amount of structured knowledge
inside the state of a Digital Audio Workstation (DAW): track roles, plug-in
chains, parameter settings, automation curves, routing, sends and buses. This
state encodes *production intent* — the decisions that turn recordings into a
finished record. AI systems that hope to *assist* rather than *replace*
producers must be able to reason over this state in a way a human can inspect
and contest.

The central object of this research is therefore an explicit, inspectable
**DAW-state graph**: a typed graph whose nodes are session entities (tracks,
descriptors, annotations, hidden-state markers) and whose edges are
relationships (contains, infers, has-descriptor, annotated-by, has-hidden-state,
supports-recommendation).

## Logic Pro as a partially observable DAW environment

Logic Pro's native project format (`.logicx`) is proprietary and, for the
purposes of open, portable tooling, effectively opaque. What a Logic workflow
*can* readily export is a set of downstream artifacts: bounced stems, a stereo
mixdown, MIDI, MusicXML, and whatever the producer chooses to document by hand.

This makes Logic a **partially observable** environment. Rather than treat that
as a limitation to be hidden, this prototype treats it as the phenomenon to be
modelled. The graph is built from evidence, and the *boundary* between what the
evidence supports and what it does not is made a first-class, visible feature.

## Exported stems are evidence, not full state

An exported stem is a *trace* of a track, not the track. From a WAV file we can
observe a filename, a duration, a sample rate, and — through descriptor
extraction — acoustic characteristics. We can *infer*, with stated confidence,
a likely role and a likely grouping. But we cannot observe the plug-in chain
that shaped it, the automation that moved through it, or the routing that placed
it in the mix. Printed processing is indistinguishable from raw recording at the
level of the exported signal.

The prototype encodes this distinction directly on every inferred track via
`observed_fields`, `inferred_fields` and `hidden_fields`, and on every graph
node via an `observability` tag (`observed` / `inferred` / `annotation` /
`hidden` / `derived`).

## Hidden-state markers support honest representation

For each class of Logic-native state that exports cannot reveal — plug-in
chains, automation, routing — the graph emits an explicit **hidden-state
marker**. Each marker names the hidden state type, describes the consequence for
downstream reasoning, and lists the evidence sources that could, in principle,
fill the gap (user notes, screenshots, partner-provided metadata, future DAW
integration).

Hidden-state markers are the heart of the research framing. They convert
"we don't know" from an implicit gap into an explicit, queryable node. An
assistant built on this representation can *say what it cannot see*.

## A formal statement of the observation model

Let **S** be the latent session state — per-track fields such as
`track_name`, `role`, `audio_content`, `plugin_chain`, `automation`, `sends`,
`bus_routing`, `track_stack`. The explorer receives a set of evidence
artifacts **E** (exported audio, MIDI, MusicXML, channel-strip notes, a
manifest, references), and each artifact type has an observation function

> **O**(artifact_type) → { *reveals*, *constrains*, *asserts*, *hides* } ⊆ fields(S)

where *reveals* marks directly observable fields, *constrains* marks fields
supporting inference with stated confidence, *asserts* marks user-provided
claims (trusted as annotations, not observations), and *hides* marks fields
this artifact cannot recover. The session graph **B** is then a belief
representation over S: every node carries an observability class
(`observed` / `inferred` / `annotation` / `hidden` / `derived`), and the graph
metadata's coverage percentages measure how much of B each class occupies.

Hidden-state markers are emitted from the model's marker catalogue: per-track
markers (the plug-in chain) are lifted when a note asserts the corresponding
field, while session-level markers (automation; routing, which folds in sends
and track stacks) are deliberately conservative — they remain even when
individual tracks carry assertions, because per-track notes do not establish
session-wide routing.

This model is not prose: it is the declarative table in
[`observation_model.py`](../src/logic_session_evidence_explorer/observation_model.py),
from which the marker catalogue, the per-track hidden-field list, and the
annotation lift are *derived* — making the table the single thing to edit when
a new evidence source (an open interchange format, partner metadata, a second
DAW) moves the observability boundary. Exports stamp the model version
(`observation_model_version`) so downstream analyses know which boundary they
were computed under.

## Audio descriptors connect structure to acoustic outcome

Descriptors (RMS, spectral centroid / bandwidth / rolloff, zero-crossing rate,
onset strength, an approximate tempo, and — when a proper loudness library is
available — LUFS) characterise the acoustic outcome of a stem. They let the
graph relate musical structure (from MIDI/MusicXML) and inferred role to
measurable signal properties, and they feed transparent heuristics (e.g. level
imbalance, low dynamic range suggestive of printed processing) without claiming
to recover the processing itself.

## Recommendations remain human-centered

The recommendation engine is deliberately rule-based and explainable. Every
recommendation carries a confidence, the related graph nodes, an explanation, a
suggested action, and a caveat. The language preserves producer agency: it
speaks of documentation and interpretability opportunities, never of a "correct"
mix. This is a design commitment, not an implementation detail — a
human-centered assistant must be legible and contestable.

## Evaluation: from asserted to measured

Role inference — the prototype's central inference step — is benchmarked
against two labeled vocabularies (see [`evaluation.md`](evaluation.md),
regenerated by `eval/benchmark_role_inference.py`):

1. the curated **instrument labels in the current MedleyDB metadata**
   (330 multitracks: the 2014 release of Bittner et al. plus later
   additions), as a proxy for the vocabulary producers type into track names,
   with out-of-taxonomy instruments expecting *abstention*; and
2. a **curated set of decorated Logic-style export filenames** (indices,
   `_Bounce`, `Stereo`, `Final`, camelCase), kept separate because it is
   synthetic.

The baseline keyword table scored 78.8% overall. Extending it with generic
production vocabulary the corpus exposed as missing ("singer", "vocalist",
"synthesizer", "cymbal", …) raised coverage to ~99% — **an in-sample number**:
the additions were selected from misses on this same corpus, so it measures
vocabulary coverage after extension, not held-out generalization. Validating
on an independent corpus (e.g. Cambridge-MT multitrack names) is the natural
next step. Remaining misses are honest tails (drum overheads and room mics,
rare percussion, "male speaker") and one instructive false positive
(`bass clarinet` → Bass). The confidence-reliability table shows the hand-set
constants are conservative: keyword matches emitted at 0.75 confidence are
correct 99.9% of the time on these vocabularies. Numbers and limits are
reported in the generated document.

## Provenance semantics: a PROV-O grounding

The session graph is a provenance graph in disguise: observed artifacts are
primary-source entities, channel-strip notes are entities *attributed to* the
producer, descriptors and analyses are entities *derived from* audio by a
software agent, and recommendations are derived from the evidence supporting
them. The export module therefore ships a **PROV-O-grounded JSON view**
(`prov_json`) — PROV-O vocabulary in a bespoke JSON layout, not the W3C
PROV-JSON serialization — mapping observability classes and edge types onto
PROV terms:

| Observability class | PROV type |
| --- | --- |
| observed | `prov:PrimarySource` |
| annotation | `lsee:UserAssertion` (attributed to the producer agent) |
| inferred | `lsee:InferredEntity` |
| derived | `prov:Entity` (generated by the tool agent) |
| hidden | `lsee:HiddenState` — an honest extension: provenance for what the evidence cannot attest |

Edge relations follow `export.PROV_EDGE_RELATIONS` (e.g. `annotated_by` →
`prov:wasAttributedTo`, `has_descriptor` / `supports_recommendation` →
`prov:wasDerivedFrom`, `contains_audio` → `prov:hadMember`). Grounding the
schema in an externally validated vocabulary gives it semantics beyond this
prototype, at essentially no implementation cost.

## Relationship to the MTG / Steinberg PhD themes

The prototype is a small, honest proof of one idea that a fuller PhD project
would develop: **DAW state can be represented in an interpretable, human-centered
way even when the native project format is proprietary or only partially
observable.** It demonstrates evidence ingestion, typed graph construction,
explicit uncertainty, and explainable assistance — all without reverse
engineering, without heavyweight models, and without overclaiming. These are
precisely the properties an industrial partner such as Steinberg and a research
group such as the MTG would need from a trustworthy AI-assisted production
system.

The natural next demonstration is the observability boundary *moving*: feeding
the same graph builder evidence from an open interchange format — DAWproject
(supported by Cubase since version 14.0.20) or AAF via `pyaaf2` — and showing
measurably fewer hidden-state markers than the Logic-export path produces.
That would establish the framework as a model of variable observability rather
than one DAW's export quirks.

## Related work

The prototype operationalizes threads from several literatures rather than
inventing its framing from scratch:

- **Intelligent music production.** De Man, Reiss & Stables (2017) survey ten
  years of automatic mixing; Moffat & Sandler (2019) review approaches and
  argue for human-in-the-loop, explainable direction. This prototype's
  human-centered recommendation language and producer-agency constraints sit
  in that lineage, applied to session *state representation* rather than
  parameter automation.
- **Interpretability / explainable AI.** Lipton (2018) distinguishes the many
  things "interpretability" is used to mean; Miller (2019) grounds machine
  explanation in how humans actually explain. The recommendation schema
  (explanation, suggested action, caveat, confidence, related evidence) is a
  direct application of that guidance.
- **Partial observability.** The observed/hidden distinction borrows its
  framing from partially observable decision processes (Kaelbling, Littman &
  Cassandra, 1998): the session graph is a belief representation, and
  hidden-state markers make the unobserved part of the state space explicit
  rather than marginalized away.
- **MIR datasets and instrument taxonomies.** MedleyDB (Bittner et al., 2014)
  provides the instrument vocabulary used to benchmark role inference, and
  Fuhrmann's UPF thesis (2012) is the reference point for what full
  audio-based instrument recognition would add beyond filename evidence.
- **Provenance.** The graph's observability semantics map onto the W3C PROV
  ontology (Lebo, Sahoo & McGuinness, 2013), which supplies externally
  validated meaning for observed/annotated/derived distinctions.
- **Interchange formats.** Bitwig's open DAWproject format (2023) and the AAF
  standard define the concrete path by which the observability boundary can
  move for the Steinberg collaboration.

### References

- Bittner, R., Salamon, J., Tierney, M., Mauch, M., Cannam, C. & Bello, J. P.
  (2014). *MedleyDB: A Multitrack Dataset for Annotation-Intensive MIR
  Research.* Proc. ISMIR.
- De Man, B., Reiss, J. D. & Stables, R. (2017). *Ten Years of Automatic
  Mixing.* Proc. 3rd Workshop on Intelligent Music Production.
- Fuhrmann, F. (2012). *Automatic musical instrument recognition from
  polyphonic music audio signals.* PhD thesis, Universitat Pompeu Fabra.
- Kaelbling, L. P., Littman, M. L. & Cassandra, A. R. (1998). *Planning and
  acting in partially observable stochastic domains.* Artificial Intelligence
  101(1–2).
- Lebo, T., Sahoo, S. & McGuinness, D. (2013). *PROV-O: The PROV Ontology.*
  W3C Recommendation.
- Lipton, Z. C. (2018). *The Mythos of Model Interpretability.* Communications
  of the ACM 61(10).
- Miller, T. (2019). *Explanation in artificial intelligence: Insights from
  the social sciences.* Artificial Intelligence 267.
- Moffat, D. & Sandler, M. B. (2019). *Approaches in Intelligent Music
  Production.* Arts 8(4).
- Bitwig GmbH & PreSonus (2023). *DAWproject: an open exchange format for DAW
  sessions.* github.com/bitwig/dawproject.
