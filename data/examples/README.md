# Example inputs

These files illustrate the optional evidence the explorer can ingest alongside
exported audio. None of them are required — the tool works from stems and a
mixdown alone — but they enrich the session graph.

| File | Purpose |
| --- | --- |
| `example_channel_strip_notes.csv` | User-provided channel-strip annotations (plug-ins, sends, buses). Treated as *annotations*, not extracted Logic state. |
| `example_session_manifest.json` | Optional manifest that can override inferred roles and add session metadata. |
| `placeholder.md` | Explains why no real audio is committed and how to generate synthetic demo audio. |

## Trying them

1. Launch the app (`streamlit run src/logic_session_evidence_explorer/app.py`).
2. Choose **Built-in demo** to generate synthetic audio automatically, or
   **Upload metadata** and attach the CSV / manifest above to your own stems.

The channel-strip notes CSV uses semicolon-separated lists inside the
`plugins` and `sends` columns, e.g. `"Channel EQ; Compressor; DeEsser"`.
