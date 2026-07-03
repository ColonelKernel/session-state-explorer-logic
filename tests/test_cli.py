from logic_session_evidence_explorer import cli
from logic_session_evidence_explorer.demo import _write_synth_wav


def test_no_descriptors_flag_after_subcommand():
    # The README-documented position: `demo --no-descriptors`.
    args = cli.build_parser().parse_args(["demo", "--no-descriptors"])
    assert args.no_descriptors is True


def test_no_descriptors_flag_before_subcommand():
    args = cli.build_parser().parse_args(["--no-descriptors", "demo"])
    assert args.no_descriptors is True


def test_scan_stems_end_to_end(tmp_path, capsys):
    _write_synth_wav(str(tmp_path / "01_Drums.wav"), "noise_burst", 0.0, seconds=0.5)
    _write_synth_wav(str(tmp_path / "02_Bass.wav"), "tone", 55.0, seconds=0.5)
    rc = cli.main(["scan-stems", str(tmp_path), "--no-descriptors"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "01_Drums.wav" in out and "Drums" in out
    assert "02_Bass.wav" in out and "Bass" in out


def test_export_bundle_end_to_end(tmp_path):
    import json

    _write_synth_wav(str(tmp_path / "01_Drums.wav"), "noise_burst", 0.0, seconds=0.5)
    out_path = tmp_path / "bundle.json"
    rc = cli.main(["export-bundle", str(tmp_path), "--no-descriptors", "--out", str(out_path)])
    assert rc == 0
    bundle = json.loads(out_path.read_text())
    assert bundle["export_metadata"]["native_project_parsed"] is False
    assert bundle["graph"]["nodes"]
