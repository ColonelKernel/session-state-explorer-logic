# About the example audio

No real audio recordings are committed to this repository. The built-in demo
("Logic Indie Mix Evidence Demo") **generates short synthetic placeholder audio
files** — simple tones and filtered noise — on demand when you run it.

These synthetic files are clearly labelled as such throughout the app and in the
exported JSON (`source_type: "synthetic_demo"`, `metadata.synthetic: true`).
They exist only to exercise the descriptor → graph → recommendation pipeline
end to end; they are not representative of a real mix.

To generate the synthetic demo audio yourself:

```bash
python -m logic_session_evidence_explorer demo --out exports/demo
```

To use your own material instead, follow
[`docs/logic_export_instructions.md`](../../docs/logic_export_instructions.md).
