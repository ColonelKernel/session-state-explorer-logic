"""Baseline regression guard (Phase 1).

Asserts the built-in demo's *deterministic* (no-descriptors) export still
matches the committed golden fixture in fixtures/baseline/. This is the
"existing extractor regression" test: every later cross-DAW phase must keep it
green. See docs/BASELINE_BEHAVIOR.md.
"""

import json
import os

from logic_session_evidence_explorer import demo, export

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "fixtures", "baseline")

# Fields that legitimately vary by machine/run (temp directories) and are
# blanked before comparison.
_VARYING_KEYS = {"file_path", "audio_dir"}


def _blank_paths(obj):
    if isinstance(obj, dict):
        return {k: ("" if k in _VARYING_KEYS else _blank_paths(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_blank_paths(v) for v in obj]
    return obj


def _load(name):
    with open(os.path.join(BASELINE, name), encoding="utf-8") as fh:
        return json.load(fh)


def _fresh_session():
    return demo.build_demo_session(with_descriptors=False)


def test_baseline_graph_matches_golden():
    fresh = json.loads(json.dumps(export.graph_json(_fresh_session()), default=str))
    assert fresh == _load("demo_graph.json")


def test_baseline_bundle_matches_golden_modulo_paths():
    fresh = json.loads(json.dumps(export.full_bundle(_fresh_session()), default=str))
    assert _blank_paths(fresh) == _blank_paths(_load("demo_full_bundle.json"))


def test_baseline_invariants():
    # The load-bearing numbers documented in BASELINE_BEHAVIOR.md.
    session = _fresh_session()
    bundle = export.full_bundle(session)
    assert session.session_name == "Logic Indie Mix Evidence Demo"
    assert session.source_type == "synthetic_demo"
    assert len(session.audio_files) == 7
    assert len(session.inferred_tracks) == 6
    assert len(session.hidden_state_markers) == 6
    assert bundle["export_metadata"]["native_project_parsed"] is False
    meta = bundle["graph"]["metadata"]
    assert meta["num_nodes"] == 36
    assert meta["num_edges"] == 35
    pct = meta["observability_percentages"]
    assert abs(sum(pct.values()) - 100.0) < 1.0
