# 90-second demo script

A tight, spoken walkthrough for a screen recording. Timings are approximate.

---

**[0:00–0:12] Opening problem**

> "DAW sessions contain rich production knowledge — plug-in chains, automation,
> routing — but proprietary project formats often hide the very states an AI
> system would need to understand. Logic Pro is a good example: what you can
> export is only part of the picture."

**[0:12–0:28] Prototype introduction**

> "Logic Session Evidence Explorer builds an interpretable graph from the
> evidence a Logic workflow *can* export: stems, a mixdown, MIDI, MusicXML, and
> user-provided channel-strip notes. I'll load the built-in demo."

*(Click **Build demo session**. The summary appears.)*

**[0:28–0:45] Walkthrough**

> "Each exported stem becomes a piece of audio evidence, linked to an inferred
> track, to audio descriptors, and to hidden-state markers. Here in the summary:
> seven audio files, six inferred tracks, descriptors extracted for each, and
> six hidden-state markers."

*(Open the **Graph** tab.)*

**[0:45–1:02] Partial observability**

> "The graph is colour-coded by observability. Blue is observed evidence, green
> is inferred state, orange is user annotations, and red is hidden Logic-native
> state — the plug-in chains, automation and routing we cannot recover from
> audio. The tool never pretends to see what the DAW hasn't exposed."

*(Toggle the **Hidden only** filter, then back to **All**.)*

**[1:02–1:18] Recommendation**

> "On the Recommendations tab, the system suggests practical, human-centered
> next steps — documenting the vocal chain, adding a reference track, or
> clarifying whether stems were exported pre- or post-fader. Every
> recommendation comes with an explanation and an explicit caveat."

*(Open the **Recommendations** tab, scroll one card.)*

**[1:18–1:30] Research value**

> "And everything exports to JSON — session evidence, the graph, descriptors,
> and recommendations — with `native_project_parsed` set to false. This
> prototype shows how AI-assisted production tools can reason *honestly* about
> DAW state, under partial observability, while keeping the producer in control."

*(Open the **Export** tab, click **Full bundle JSON**.)*

---

## Recording tips

- Run `streamlit run src/logic_session_evidence_explorer/app.py` beforehand and
  pre-click **Build demo session** once so audio is generated and cached.
- Record at 1280×800 or larger; the graph benefits from width.
- Keep the sidebar visible so the four modes are on screen.
