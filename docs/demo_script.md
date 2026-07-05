# 90-second demo script

A tight, spoken walkthrough for a screen recording, written against the
current UI (evidence meter, layered-by-observability graph as the default
view, evidence-linked recommendations, stem-sum reconciliation, PROV export).
Timings are approximate; the demo numbers quoted below are what the built-in
demo actually produces.

---

**[0:00–0:12] Opening problem** *(app open in Built-in demo mode, nothing built)*

> "DAW sessions contain rich production knowledge — plug-in chains,
> automation, routing — but proprietary project formats hide the very states
> an AI system would need to understand. Logic Pro is a good example: what
> you can export is only part of the picture."

**[0:12–0:30] Build + the evidence meter** *(click **Build demo session**)*

> "Logic Session Evidence Explorer builds an interpretable graph from what a
> Logic workflow *can* export. Here's the built-in demo: seven audio files,
> six inferred tracks, six hidden-state markers. And this bar is the whole
> thesis in one glance — how much of the session graph is directly observed,
> how much is inferred, how much came from the producer's notes, and how much
> is explicitly *hidden*: about seventeen percent observed, thirteen percent
> hidden."

*(Point at the stacked observability bar and the provenance caption
"Built from: synthetic demo".)*

**[0:30–0:52] The layered graph** *(Graph tab — the layered view is the default)*

> "The graph lays the evidence out by observability: observed exports on the
> left, then inferred tracks, the producer's channel-strip notes in orange,
> and in red the Logic-native state no export can reveal — plug-in chains,
> automation, routing. On the far right, everything the tool derived:
> descriptors, and a stem-sum reconciliation that measured a near-zero-dB
> residual — signal evidence that this mixdown contains processing the stems
> don't explain. The tool never pretends to see what the DAW hasn't exposed."

*(Sweep the cursor left to right across the columns; hover one red
"Hidden plug-in chain" marker so the tooltip states what cannot be
observed from exports.)*

**[0:52–1:12] Evidence-linked recommendations** *(Recommendations tab)*

> "Recommendations are rule-based and explainable — each one carries a
> confidence, an explanation, a suggested action, and a caveat, and names its
> evidence. This one says the vocal processing state is under-documented,
> and it points at exactly one stem: the backing vocals — the lead vocal has
> notes. Click 'Highlight in graph'…"

*(Click **Highlight in graph** on the vocal card, switch to the Graph tab —
the backing-vocals nodes render enlarged and outlined.)*

> "…and the graph shows precisely which evidence the claim rests on."

**[1:12–1:30] Exports + research value** *(Export tab)*

> "Everything exports to JSON — the session evidence, the graph, and a
> PROV-O-grounded provenance view — always stamped with
> `native_project_parsed: false`. This prototype shows how AI-assisted
> production systems can reason *honestly* about DAW state, under partial
> observability, while keeping the producer in control."

*(Click **Full bundle JSON**; end on the Export tab or cut back to the
evidence meter.)*

---

## Pre-flight checklist (before recording)

- [ ] `streamlit run src/logic_session_evidence_explorer/app.py` — the repo's
      `.streamlit/config.toml` supplies the blue theme; don't override it
- [ ] Build the demo session once and discard that take: synthetic audio and
      descriptor extraction are cached afterwards, so the on-camera build is
      instant
- [ ] Click **Clear highlight** if a highlight is active from rehearsal, and
      rebuild the demo session so node ids match the recommendations
- [ ] Confirm the Graph tab shows the **Layered by observability** layout
      (the default) and the whole graph is in frame — it auto-fits on render
- [ ] Record at 1440×900 or larger, browser at 100% zoom, sidebar visible so
      the four modes are on screen
- [ ] Keep the Legend & filters expander open — the colour/shape caption is
      part of the story
- [ ] Optional beat if you have 10 spare seconds: the **Listen to audio
      evidence** expander in the Tables tab — playing a stem next to its
      inferred role lands "inspect and contest" instantly

## Screenshot checklist (`docs/screenshots/`)

- [ ] Landing view: header, framing box, sidebar modes (nothing built)
- [ ] Session summary with the evidence meter and provenance caption
- [ ] Layered graph, full frame, legend expander open
- [ ] Graph with **Hidden only** observability focus (red markers isolated)
- [ ] Graph with a recommendation's evidence highlighted (enlarged nodes +
      "Highlighting evidence for:" caption)
- [ ] Recommendations tab: the vocal card showing explanation, action,
      caveat, and the evidence chip
- [ ] Tables tab: stem-sum reconciliation metrics + band-residual chart
- [ ] Tables tab: audio playback expander open on a stem
- [ ] Export tab: the six download buttons
- [ ] About / limitations page

## Talking-point numbers (built-in demo, for accuracy)

| Fact | Value |
| --- | --- |
| Audio files / inferred tracks | 7 / 6 |
| Hidden-state markers | 6 (automation, routing, 4× plug-in chain) |
| Recommendations | 5 |
| Observability split | ~17% observed · ~13% inferred · ~30% annotation · ~13% hidden · ~28% derived |
| Stem-sum residual | −0.27 dB ("substantial residual" tier — the synthetic mixdown is deliberately *not* the stem sum) |
| Vocal rule evidence | Backing Vocals Bounce only (Lead Vocal is documented by notes) |
