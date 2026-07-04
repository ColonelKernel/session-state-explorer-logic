"""Streamlit UI for the Logic Session Evidence Explorer.

Run with::

    streamlit run src/logic_session_evidence_explorer/app.py

The app is organised around the four modes described in the research prototype
spec: built-in demo, upload Logic exports, upload metadata, and export bundle.
It always foregrounds the distinction between observed, inferred, annotated and
hidden state.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

# Allow ``streamlit run path/to/app.py`` to import the package.
_PKG_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)

import streamlit as st  # noqa: E402

from logic_session_evidence_explorer import (  # noqa: E402
    aaf_adm_inspector,
    demo,
    export,
    graph_builder,
    manifest_loader,
    midi_inspector,
    musicxml_inspector,
    session_builder,
    stem_scanner,
    utils,
    visualization,
)
from logic_session_evidence_explorer.models import (  # noqa: E402
    ReferenceTrackEvidence,
    SessionEvidence,
)

st.set_page_config(page_title="Logic Session Evidence Explorer v0", layout="wide")

RESEARCH_FRAMING = (
    "Logic Pro projects contain rich production state, but exported files reveal "
    "only part of that state. This prototype builds a graph from observable "
    "evidence, inferred track roles, audio descriptors, and explicit hidden-state "
    "markers."
)
LIMITATIONS = (
    "This prototype does not parse proprietary Logic project internals. It works "
    "from exported evidence and user-provided annotations. Native plug-in chains, "
    "automation, sends, buses, and track stacks may remain hidden unless "
    "separately documented."
)


def _save_upload(upload, subdir: str) -> str:
    """Persist a Streamlit UploadedFile to a temp path and return the path."""

    base = os.path.join(tempfile.gettempdir(), "lsee_uploads", subdir)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, upload.name)
    with open(path, "wb") as fh:
        fh.write(upload.getbuffer())
    return path


# --------------------------------------------------------------------------- #
# Session construction from uploads
# --------------------------------------------------------------------------- #
def build_session_from_uploads(state: dict) -> SessionEvidence:
    utils.reset_ids()

    scanned: list[stem_scanner.ScannedFile] = []
    # A stem upload sharing the dedicated reference's filename is the same
    # file: mark it as a reference so it is not double-counted as a stem.
    reference_names: set[str] = set()
    if state.get("reference"):
        reference_names.add(state["reference"].name)

    for up in state.get("stems", []):
        path = _save_upload(up, "stems")
        scanned.append(stem_scanner.ScannedFile(file_name=up.name, file_path=path, upload_name=up.name))
    if state.get("mixdown"):
        up = state["mixdown"]
        path = _save_upload(up, "mixdown")
        scanned.append(stem_scanner.ScannedFile(file_name=up.name, file_path=path, upload_name=up.name))

    audio_files = stem_scanner.scan_files(scanned, reference_names=reference_names)
    # Force the explicitly-uploaded mixdown to be a mixdown.
    if state.get("mixdown"):
        for a in audio_files:
            if a.upload_name == state["mixdown"].name:
                a.is_mixdown = True
                a.is_reference = False

    session = SessionEvidence(
        session_name=state.get("session_name") or "Uploaded Logic Exports",
        source_type="logic_exports",
        audio_files=audio_files,
    )

    # Reference track (separate uploader).
    if state.get("reference"):
        up = state["reference"]
        path = _save_upload(up, "reference")
        session.reference_tracks.append(
            ReferenceTrackEvidence(id=utils.make_id("reference"), file_name=up.name, file_path=path)
        )

    # Channel-strip notes.
    if state.get("notes"):
        up = state["notes"]
        text = up.getvalue().decode("utf-8", errors="replace")
        notes, warnings = manifest_loader.load_channel_strip_notes(text, file_name=up.name)
        session.channel_strip_notes = notes
        session.warnings.extend(warnings)

    # Session manifest (role/notes overrides + metadata).
    if state.get("manifest"):
        up = state["manifest"]
        result = manifest_loader.load_manifest_text(up.getvalue().decode("utf-8", errors="replace"))
        if result.session_name:
            session.session_name = result.session_name
        if result.daw_version:
            session.daw_version = result.daw_version
        session.warnings.extend(result.warnings)
        for a in session.audio_files:
            if a.file_name in result.role_overrides:
                a.inferred_role = result.role_overrides[a.file_name]
                a.role_explanation = "Role set by session manifest."
                a.confidence = max(a.confidence, 0.9)

    # MIDI / MusicXML.
    if state.get("midi"):
        up = state["midi"]
        path = _save_upload(up, "midi")
        session.midi_evidence = midi_inspector.inspect_midi(path, file_name=up.name)
    if state.get("musicxml"):
        up = state["musicxml"]
        path = _save_upload(up, "musicxml")
        session.musicxml_evidence = musicxml_inspector.inspect_musicxml(path, file_name=up.name)

    # AAF / ADM interchange file (conservative inspection only).
    if state.get("interchange"):
        up = state["interchange"]
        path = _save_upload(up, "interchange")
        result = aaf_adm_inspector.inspect_interchange_file(path, file_name=up.name)
        session.metadata["interchange_evidence"] = result
        session.warnings.extend(result.get("warnings", []))

    return session_builder.finalize_session(
        session, with_descriptors=state.get("with_descriptors", True)
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render_evidence_meter(session: SessionEvidence) -> None:
    """One stacked bar showing how much of the graph is observed vs inferred
    vs annotated vs hidden vs derived — the thesis of the tool, in one glance."""

    metadata = graph_builder.build_graph_export(session).metadata
    pcts = metadata.get("observability_percentages", {})
    segments = ""
    labels = []
    for key in visualization.OBSERVABILITY_ORDER:
        pct = pcts.get(key, 0)
        if pct <= 0:
            continue
        color = visualization.OBSERVABILITY_COLORS[key]
        segments += (
            f'<div style="width:{pct}%;background:{color};" '
            f'title="{key}: {pct}%"></div>'
        )
        labels.append(
            f'<span style="color:{color};font-weight:600">{pct:g}% {key}</span>'
        )
    st.markdown(
        '<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;'
        f'border:1px solid #ddd">{segments}</div>'
        f'<div style="margin-top:4px;font-size:0.85em">{" · ".join(labels)}</div>',
        unsafe_allow_html=True,
    )


def render_summary(session: SessionEvidence) -> None:
    st.subheader("Session summary")
    provenance = (
        "synthetic demo (generated audio)"
        if session.source_type == "synthetic_demo"
        else "your uploaded Logic exports"
    )
    st.caption(f"Built from: {provenance}")
    render_evidence_meter(session)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Audio files", len(session.audio_files))
    c1.metric("Inferred tracks", len(session.inferred_tracks))
    c2.metric("Descriptors", len(session.descriptors))
    c2.metric("Channel-strip notes", len(session.channel_strip_notes))
    c3.metric("Hidden-state markers", len(session.hidden_state_markers))
    c3.metric("Recommendations", len(session.recommendations))
    c4.metric("Mixdown present", "Yes" if any(a.is_mixdown for a in session.audio_files) else "No")
    c4.metric("Reference present",
              "Yes" if (session.reference_tracks or any(a.is_reference for a in session.audio_files)) else "No")
    extra1, extra2 = st.columns(2)
    extra1.write(f"**MIDI present:** {'Yes' if session.midi_evidence else 'No'}")
    extra2.write(f"**MusicXML present:** {'Yes' if session.musicxml_evidence else 'No'}")
    if session.warnings:
        with st.expander(f"Warnings ({len(session.warnings)})"):
            for w in session.warnings:
                st.write(f"- {w}")


def render_tables(session: SessionEvidence) -> None:
    import pandas as pd

    st.subheader("Audio evidence")
    st.dataframe(pd.DataFrame([{
        "file_name": a.file_name,
        "track_index": a.track_index,
        "inferred_role": a.inferred_role,
        "is_mixdown": a.is_mixdown,
        "is_reference": a.is_reference,
        "duration_s": round(a.duration_seconds, 2) if a.duration_seconds else None,
        "confidence": a.confidence,
        "explanation": a.role_explanation,
    } for a in session.audio_files]), use_container_width=True)

    playable = [
        a for a in session.audio_files if a.file_path and os.path.exists(a.file_path)
    ]
    playable_refs = [
        r for r in session.reference_tracks if r.file_path and os.path.exists(r.file_path)
    ]
    if playable or playable_refs:
        with st.expander("Listen to audio evidence"):
            st.caption(
                "Hearing a stem next to its inferred role is the fastest way to "
                "inspect — and contest — the inference."
            )
            options: dict = {}
            for a in playable:
                label = f"{a.inferred_track_name or a.file_name} ({a.inferred_role})"
                # Distinct files can normalise to the same display name;
                # disambiguate so every file stays auditable.
                if label in options:
                    label = f"{label} — {a.file_name}"
                while label in options:
                    label += " (duplicate)"
                options[label] = a.file_path
            for r in playable_refs:
                options[f"Reference: {r.file_name}"] = r.file_path
            choice = st.selectbox("Audio file", list(options))
            st.audio(options[choice])

    st.subheader("Inferred tracks")
    st.dataframe(pd.DataFrame([{
        "name": t.name,
        "role": t.role,
        "confidence": t.confidence,
        "observed": ", ".join(t.observed_fields),
        "inferred": ", ".join(t.inferred_fields),
        "hidden": ", ".join(t.hidden_fields),
    } for t in session.inferred_tracks]), use_container_width=True)

    recon = session.stem_sum_reconciliation
    if recon:
        st.subheader("Stem-sum reconciliation")
        st.caption(
            "The exported stems were summed, one global gain was fitted, and "
            "the residual against the mixdown was measured. Signal evidence "
            "for how much of the mix the stems explain."
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Residual", f"{recon.residual_db} dB" if recon.residual_db is not None else "n/a")
        m2.metric("Correlation", recon.correlation if recon.correlation is not None else "n/a")
        m3.metric("Fitted gain", recon.fitted_gain if recon.fitted_gain is not None else "n/a")
        st.write(recon.interpretation)
        if recon.band_residuals_db:
            st.bar_chart(pd.DataFrame(
                {"residual_db": recon.band_residuals_db}
            ))
        for w in recon.warnings:
            st.caption(f"⚠️ {w}")

    for cmp_result in session.reference_comparisons:
        st.subheader("Reference comparison")
        st.caption(
            "Per-band energy fractions (level-independent): positive bars mean "
            "the mixdown has proportionally more energy in that band than the "
            "reference. A reference is a comparison, not a target."
        )
        if cmp_result.band_deltas_db:
            st.bar_chart(pd.DataFrame({"delta_db_vs_reference": cmp_result.band_deltas_db}))
        details = {
            "LUFS delta": cmp_result.lufs_delta,
            "Crest delta (dB)": cmp_result.crest_delta_db,
            "Stereo width delta": cmp_result.stereo_width_delta,
        }
        st.write({k: v for k, v in details.items() if v is not None})
        if cmp_result.summary:
            st.write(cmp_result.summary)
        for w in cmp_result.warnings:
            st.caption(f"⚠️ {w}")

    if session.descriptors:
        st.subheader("Audio descriptors")
        st.dataframe(pd.DataFrame([{
            "file_name": d.file_name,
            "duration_s": round(d.duration_seconds, 2) if d.duration_seconds else None,
            "rms_mean": d.rms_mean,
            "active_rms": d.active_rms_mean,
            "activity": d.activity_ratio,
            "peak": d.peak_amplitude,
            "dyn_range_dB": d.dynamic_range_approx,
            "active_crest_dB": d.dynamic_range_active_db,
            "stereo_width": d.stereo_width_ratio,
            "centroid_hz": round(d.spectral_centroid_mean, 1) if d.spectral_centroid_mean else None,
            "zcr": d.zero_crossing_rate_mean,
            "tempo": d.estimated_tempo,
            "LUFS": d.integrated_loudness_lufs,
        } for d in session.descriptors]), use_container_width=True)

    if session.channel_strip_notes:
        st.subheader("Channel-strip notes (user-provided annotations)")
        st.dataframe(pd.DataFrame([{
            "track_name": n.track_name,
            "role": n.role,
            "plugins": "; ".join(n.plugins),
            "sends": "; ".join(n.sends),
            "bus": n.bus,
            "notes": n.notes,
        } for n in session.channel_strip_notes]), use_container_width=True)

    if session.midi_evidence:
        m = session.midi_evidence
        st.subheader("MIDI summary")
        st.json({
            "file_name": m.file_name, "track_count": m.track_count, "note_count": m.note_count,
            "tempo_estimates": m.tempo_estimates, "time_signatures": m.time_signatures,
            "track_names": m.track_names, "instrument_names": m.instrument_names,
            "note_range": m.note_range, "warnings": m.warnings,
        })

    if session.musicxml_evidence:
        x = session.musicxml_evidence
        st.subheader("MusicXML summary")
        st.caption("MusicXML describes score / notation evidence, not mix state.")
        st.json({
            "file_name": x.file_name, "part_count": x.part_count, "measure_count": x.measure_count,
            "part_names": x.part_names, "detected_keys": x.detected_keys,
            "detected_time_signatures": x.detected_time_signatures, "warnings": x.warnings,
        })

    if session.metadata.get("interchange_evidence"):
        st.subheader("AAF / ADM interchange evidence")
        st.caption("Recorded as external interchange evidence; not fully parsed.")
        st.json(session.metadata["interchange_evidence"])

    st.subheader("Hidden-state markers")
    st.dataframe(pd.DataFrame([{
        "type": h.hidden_state_type,
        "description": h.description,
        "consequence": h.consequence,
    } for h in session.hidden_state_markers]), use_container_width=True)


def render_graph(session: SessionEvidence) -> None:
    st.subheader("Interpretable session graph")

    with st.expander("Legend & filters", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            show_desc = st.checkbox("Show descriptors", value=True)
            show_hidden = st.checkbox("Show hidden-state markers", value=True)
            show_rec = st.checkbox("Show recommendations", value=True)
            show_score = st.checkbox("Show MIDI / MusicXML", value=True)
        with cols[1]:
            obs_filter = st.selectbox(
                "Observability focus",
                ["All", "Observed only", "Inferred only", "Annotations only",
                 "Hidden only", "Derived only"],
            )
        with cols[2]:
            layout_choice = st.selectbox(
                "Layout",
                ["Force-directed", "Layered by observability"],
                help="Layered columns run observed → inferred → annotation → "
                     "hidden → derived, left to right.",
            )
        legend_html = " &nbsp; ".join(
            f'<span style="color:{visualization.OBSERVABILITY_COLORS[obs]};font-weight:600">&#9679; {label}</span>'
            for label, obs in visualization.LEGEND
        )
        st.markdown(legend_html, unsafe_allow_html=True)

    highlight_ids = st.session_state.get("highlight_ids") or []
    if highlight_ids:
        hl_col, clear_col = st.columns([4, 1])
        hl_col.caption(
            f"Highlighting evidence for: {st.session_state.get('highlight_title', '')}"
        )
        clear_col.button("Clear highlight", on_click=_clear_highlight)

    obs_map = {
        "All": None, "Observed only": "observed", "Inferred only": "inferred",
        "Annotations only": "annotation", "Hidden only": "hidden",
        "Derived only": "derived",
    }
    layout = "layered" if layout_choice.startswith("Layered") else "force"
    filters = dict(
        show_descriptors=show_desc, show_hidden=show_hidden,
        show_recommendations=show_rec, show_score=show_score,
        observability_only=obs_map[obs_filter],
    )

    try:
        html = visualization.build_pyvis_html(
            session, layout=layout, highlight_ids=highlight_ids, **filters
        )
        import streamlit.components.v1 as components

        components.html(html, height=680, scrolling=True)
        return
    except Exception as exc:
        st.info(f"PyVis unavailable ({exc}); falling back to Plotly.")

    try:
        fig = visualization.build_plotly_figure(
            session, layout=layout, highlight_ids=highlight_ids, **filters
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.warning(f"Graph rendering unavailable ({exc}). Showing raw graph JSON.")
        st.json(export.graph_json(session))


def _set_highlight(title: str, node_ids: list) -> None:
    """on_click callback: runs before the script re-executes, so the graph
    (rendered earlier in the script than the recommendations) sees the new
    highlight in the same frame the user's click produces."""

    st.session_state["highlight_ids"] = list(node_ids)
    st.session_state["highlight_title"] = title
    st.toast("Open the Graph tab to see the highlighted evidence.")


def _clear_highlight() -> None:
    st.session_state["highlight_ids"] = []
    st.session_state["highlight_title"] = ""


def _store_session(session: SessionEvidence) -> None:
    """Replace the active session; any highlight refers to the old session's
    node ids (which a rebuild reuses for different nodes), so drop it."""

    _clear_highlight()
    st.session_state["session"] = session


def _node_label_map(session: SessionEvidence) -> dict:
    labels = {}
    for a in session.audio_files:
        labels[a.id] = a.inferred_track_name or a.file_name
    for t in session.inferred_tracks:
        labels[t.id] = t.name
    for r in session.reference_tracks:
        labels[r.id] = r.file_name
    for n in session.channel_strip_notes:
        labels[n.id] = f"Notes: {n.track_name}"
    return labels


def render_recommendations(session: SessionEvidence) -> None:
    st.subheader("Explainable recommendations")
    if not session.recommendations:
        st.success("No recommendations fired for this session.")
        return
    labels = _node_label_map(session)
    sev_icon = {"info": "ℹ️", "suggestion": "💡", "warning": "⚠️"}
    for rec in session.recommendations:
        with st.container(border=True):
            st.markdown(f"### {sev_icon.get(rec.severity, '•')} {rec.title}")
            st.caption(f"Severity: {rec.severity} · Confidence: {rec.confidence:.2f}")
            st.write(f"**Explanation:** {rec.explanation}")
            st.write(f"**Suggested action:** {rec.suggested_action}")
            st.write(f"**Caveat:** {rec.caveat}")
            evidence = [labels.get(nid, nid) for nid in rec.related_node_ids]
            if evidence:
                chips = " ".join(f"`{name}`" for name in evidence)
                st.markdown(f"**Evidence:** {chips}")
                st.button(
                    "Highlight in graph",
                    key=f"highlight_{rec.id}",
                    on_click=_set_highlight,
                    args=(rec.title, rec.related_node_ids),
                )


def render_exports(session: SessionEvidence) -> None:
    st.subheader("Export research bundle")
    dumps = utils.dumps
    c1, c2, c3 = st.columns(3)
    c1.download_button("Session evidence JSON", dumps(export.session_evidence_json(session)),
                       file_name="session_evidence.json", mime="application/json")
    c1.download_button("Graph JSON", dumps(export.graph_json(session)),
                       file_name="graph.json", mime="application/json")
    c2.download_button("Descriptors JSON", dumps(export.descriptors_json(session)),
                       file_name="descriptors.json", mime="application/json")
    c2.download_button("Recommendations JSON", dumps(export.recommendations_json(session)),
                       file_name="recommendations.json", mime="application/json")
    c3.download_button("Full bundle JSON", dumps(export.full_bundle(session)),
                       file_name="full_bundle.json", mime="application/json", type="primary")
    c3.download_button("PROV-O JSON view", dumps(export.prov_json(session)),
                       file_name="session_prov.json", mime="application/json",
                       help="PROV-O-grounded JSON view of the session graph: observed "
                            "evidence as primary sources, notes attributed to the "
                            "producer, analyses as derivations, hidden state as an "
                            "honest extension class.")


def render_session(session: SessionEvidence) -> None:
    render_summary(session)
    tab_graph, tab_tables, tab_rec, tab_export = st.tabs(
        ["Graph", "Tables", "Recommendations", "Export"]
    )
    with tab_graph:
        render_graph(session)
    with tab_tables:
        render_tables(session)
    with tab_rec:
        render_recommendations(session)
    with tab_export:
        render_exports(session)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.title("Logic Session Evidence Explorer v0")
    st.markdown(
        "*Interpretable DAW-state graphs from Logic Pro exports and partial session evidence*"
    )
    st.info(RESEARCH_FRAMING)

    mode = st.sidebar.radio(
        "Mode",
        ["Built-in demo", "Upload Logic exports", "Upload metadata", "About / limitations"],
    )
    with_descriptors = st.sidebar.checkbox(
        "Extract audio descriptors", value=True,
        help="Requires librosa. Disable for a faster, filename-only pass.",
    )

    if mode == "Built-in demo":
        st.header("Mode 1 — Built-in demo")
        st.caption("Loads the synthetic 'Logic Indie Mix Evidence Demo'. Audio is generated tones/noise.")
        if st.button("Build demo session", type="primary"):
            with st.spinner("Generating synthetic audio and building the graph..."):
                _store_session(demo.build_demo_session(with_descriptors=with_descriptors))
        if st.session_state.get("session"):
            render_session(st.session_state["session"])

    elif mode in ("Upload Logic exports", "Upload metadata"):
        st.header(f"Mode — {mode}")
        state: dict = {"with_descriptors": with_descriptors}
        state["session_name"] = st.text_input("Session name", value="Uploaded Logic Exports")

        st.markdown("**Audio evidence**")
        state["stems"] = st.file_uploader(
            "Exported stems / bounced tracks", type=["wav", "aif", "aiff", "flac", "mp3"],
            accept_multiple_files=True,
        )
        col = st.columns(2)
        with col[0]:
            state["mixdown"] = st.file_uploader("Stereo mixdown", type=["wav", "aif", "aiff", "flac", "mp3"])
        with col[1]:
            state["reference"] = st.file_uploader("Reference track", type=["wav", "aif", "aiff", "flac", "mp3"])

        if mode == "Upload metadata":
            st.markdown("**Metadata enrichment**")
            mcol = st.columns(2)
            with mcol[0]:
                state["midi"] = st.file_uploader("MIDI file", type=["mid", "midi"])
                state["notes"] = st.file_uploader("Channel-strip notes", type=["csv", "json"])
            with mcol[1]:
                state["musicxml"] = st.file_uploader("MusicXML file", type=["xml", "musicxml", "mxl"])
                state["manifest"] = st.file_uploader("Session manifest JSON", type=["json"])
            state["interchange"] = st.file_uploader(
                "AAF / ADM interchange file (recorded as external evidence, not fully parsed)",
                type=["aaf", "adm", "xml"],
            )

        if st.button("Build session from uploads", type="primary"):
            if not state["stems"] and not state.get("mixdown"):
                st.warning("Upload at least one stem or a mixdown to build a session.")
            else:
                with st.spinner("Scanning evidence and building the graph..."):
                    _store_session(build_session_from_uploads(state))
        if st.session_state.get("session"):
            render_session(st.session_state["session"])

    else:  # About / limitations
        st.header("About & limitations")
        st.warning(LIMITATIONS)
        st.markdown(
            "This prototype does not attempt full Logic Pro project reconstruction, "
            "proprietary `.logicx` parsing, or autonomous mixing. It demonstrates how "
            "exported DAW evidence can be represented, inspected, enriched, and used "
            "for explainable production assistance under partial observability."
        )
        st.markdown("**Node observability legend**")
        st.markdown(
            " &nbsp; ".join(
                f'<span style="color:{c};font-weight:600">&#9679; {k}</span>'
                for k, c in visualization.OBSERVABILITY_COLORS.items() if k != "unknown"
            ),
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("---")
    st.sidebar.caption("Research prototype · evidence-based · native project not parsed")


# ``streamlit run app.py`` executes the module with ``__name__ == "__main__"``.
if __name__ == "__main__":
    main()
