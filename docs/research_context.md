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
