"""Command-line interface for the Logic Session Evidence Explorer.

Examples
--------
    python -m logic_session_evidence_explorer demo --out exports/demo
    python -m logic_session_evidence_explorer scan-stems path/to/stems
    python -m logic_session_evidence_explorer export-bundle path/to/stems --out bundle.json
"""

from __future__ import annotations

import argparse
import os
import sys

from . import demo, export, session_builder, stem_scanner, utils
from .models import SessionEvidence


def _write_outputs(session: SessionEvidence, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    utils.write_json(os.path.join(out_dir, "session_evidence.json"), export.session_evidence_json(session))
    utils.write_json(os.path.join(out_dir, "graph.json"), export.graph_json(session))
    utils.write_json(os.path.join(out_dir, "descriptors.json"), export.descriptors_json(session))
    utils.write_json(os.path.join(out_dir, "recommendations.json"), export.recommendations_json(session))
    utils.write_json(os.path.join(out_dir, "full_bundle.json"), export.full_bundle(session))
    print(f"Wrote 5 JSON files to {out_dir}")


def _build_from_folder(folder: str, *, with_descriptors: bool) -> SessionEvidence:
    utils.reset_ids()
    audio_files = stem_scanner.scan_folder(folder)
    session = SessionEvidence(
        session_name=os.path.basename(os.path.abspath(folder)) or "Logic Exports",
        source_type="logic_exports",
        audio_files=audio_files,
    )
    return session_builder.finalize_session(session, with_descriptors=with_descriptors)


def cmd_demo(args: argparse.Namespace) -> int:
    session = demo.build_demo_session(with_descriptors=not getattr(args, "no_descriptors", False))
    print(f"Built demo session '{session.session_name}' with {len(session.audio_files)} audio files, "
          f"{len(session.inferred_tracks)} inferred tracks, "
          f"{len(session.hidden_state_markers)} hidden-state markers, "
          f"{len(session.recommendations)} recommendations.")
    if args.out:
        _write_outputs(session, args.out)
    return 0


def cmd_scan_stems(args: argparse.Namespace) -> int:
    if not os.path.isdir(args.folder):
        print(f"Not a directory: {args.folder}", file=sys.stderr)
        return 2
    session = _build_from_folder(args.folder, with_descriptors=not getattr(args, "no_descriptors", False))
    print(f"Scanned {len(session.audio_files)} audio files:")
    for a in session.audio_files:
        tag = "mixdown" if a.is_mixdown else ("reference" if a.is_reference else a.inferred_role)
        print(f"  [{a.track_index if a.track_index is not None else '-'}] {a.file_name} -> "
              f"{tag} (confidence {a.confidence:.2f})")
    if args.out:
        _write_outputs(session, args.out)
    return 0


def cmd_export_bundle(args: argparse.Namespace) -> int:
    if not os.path.isdir(args.folder):
        print(f"Not a directory: {args.folder}", file=sys.stderr)
        return 2
    session = _build_from_folder(args.folder, with_descriptors=not getattr(args, "no_descriptors", False))
    utils.write_json(args.out, export.full_bundle(session))
    print(f"Wrote research bundle to {args.out}")
    return 0


def cmd_export_canonical_bundle(args: argparse.Namespace) -> int:
    """Export the five-file v0.2 canonical wire bundle (analyzer contract)."""
    # Imported lazily: needs the optional canonical-snapshot package.
    from .canonical_export import export_bundle

    result = export_bundle(
        args.input,
        args.out,
        with_descriptors=not getattr(args, "no_descriptors", False),
        sanitize=not args.no_sanitize,
        notes_path=args.notes,
    )
    print(f"Wrote canonical bundle ({', '.join(result['files'])}) to {result['out_dir']}")
    print(f"snapshot_id={result['snapshot_id']} valid={result['valid']}")
    return 0 if result["valid"] else 1


def build_parser() -> argparse.ArgumentParser:
    # Shared flags, attached to every subcommand so both positions work:
    # `... demo --no-descriptors` and `... --no-descriptors demo`.
    # SUPPRESS keeps a subparser's default from clobbering a value the
    # top-level parser already set; read with getattr(..., False).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-descriptors", action="store_true",
                        default=argparse.SUPPRESS,
                        help="Skip audio descriptor extraction (faster, no librosa needed).")

    parser = argparse.ArgumentParser(
        prog="logic_session_evidence_explorer",
        description="Build interpretable DAW-state graphs from Logic Pro exports.",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", parents=[common],
                            help="Build the built-in synthetic demo session.")
    p_demo.add_argument("--out", help="Directory to write JSON exports into.")
    p_demo.set_defaults(func=cmd_demo)

    p_scan = sub.add_parser("scan-stems", parents=[common],
                            help="Scan a folder of exported stems.")
    p_scan.add_argument("folder", help="Folder containing exported audio files.")
    p_scan.add_argument("--out", help="Directory to write JSON exports into.")
    p_scan.set_defaults(func=cmd_scan_stems)

    p_bundle = sub.add_parser("export-bundle", parents=[common],
                              help="Scan a folder and write the full bundle JSON.")
    p_bundle.add_argument("folder", help="Folder containing exported audio files.")
    p_bundle.add_argument("--out", default="bundle.json", help="Output JSON path.")
    p_bundle.set_defaults(func=cmd_export_bundle)

    p_wire = sub.add_parser(
        "export-canonical-bundle", parents=[common],
        help="Export the five-file v0.2 canonical snapshot bundle "
             "(requires the canonical-snapshot package).")
    p_wire.add_argument(
        "input",
        help="Evidence folder, session manifest .json, 'demo', or 'demo-full' "
             "(the synthetic full-evidence demo: stems + exact-sum mixdown + "
             "reference + MIDI + MusicXML + notes).")
    p_wire.add_argument("--out", default="exports/canonical",
                        help="Directory to write the bundle into.")
    p_wire.add_argument("--notes", help="Optional channel-strip notes CSV/JSON path.")
    p_wire.add_argument("--no-sanitize", action="store_true",
                        help="Keep raw home/temp paths in the exported bundle.")
    p_wire.set_defaults(func=cmd_export_canonical_bundle)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
