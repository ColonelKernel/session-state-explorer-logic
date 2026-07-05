"""Phase B: canonical schema + validation."""

import json

from logic_session_evidence_explorer.canonical import schema as S
from logic_session_evidence_explorer.canonical.validation import (
    is_compatible,
    migrate_snapshot,
    validate_snapshot,
)


def _minimal_snapshot():
    return S.CanonicalDAWSnapshot(
        snapshot_id="snap_1",
        source=S.Source(daw="logic", adapter="logic", adapter_version="0.2.0",
                        capture_modes=["exported_interchange"]),
        project=S.CanonicalEntity(id="proj_1", kind="project", name="Demo"),
        entities=S.Entities(
            tracks=[S.CanonicalEntity(id="tr_1", kind="track", name="Drums",
                                      refs={"channel": "ch_1"})],
            channels=[S.CanonicalEntity(id="ch_1", kind="channel", name="Drums",
                                        evidence="inferred")],
            hidden_states=[S.CanonicalEntity(id="hid_1", kind="hidden_state",
                                             evidence="hidden", availability="inaccessible")],
        ),
        graph=S.CanonicalGraph(
            nodes=[S.CanonicalNode(id="tr_1", label="Drums", type="track"),
                   S.CanonicalNode(id="ch_1", label="Drums", type="channel", evidence="inferred")],
            edges=[S.CanonicalEdge(source="tr_1", target="ch_1", type="uses_channel")],
        ),
    )


def test_schema_version_is_0_2_0():
    assert S.CANONICAL_SCHEMA_VERSION == "0.2.0"
    assert _minimal_snapshot().schema_version == "0.2.0"


def test_snapshot_round_trips_json():
    snap = _minimal_snapshot()
    d = S.snapshot_to_dict(snap)
    text = json.dumps(d)
    back = json.loads(text)
    assert back["source"]["daw"] == "logic"
    assert back["entities"]["tracks"][0]["refs"]["channel"] == "ch_1"
    # Provenance/extensions survive as inspectable structure.
    assert back["entities"]["hidden_states"][0]["availability"] == "inaccessible"


def test_valid_snapshot_passes():
    report = validate_snapshot(_minimal_snapshot())
    assert report.ok, report.errors


def test_dangling_ref_warns_not_errors():
    snap = _minimal_snapshot()
    snap.entities.tracks[0].refs["channel"] = "ch_missing"
    report = validate_snapshot(snap)
    assert report.ok  # dangling ref is a warning, not a hard error
    assert any("ch_missing" in w for w in report.warnings)


def test_edge_to_missing_node_errors():
    snap = _minimal_snapshot()
    snap.graph.edges.append(S.CanonicalEdge(source="tr_1", target="ghost", type="routes_to"))
    report = validate_snapshot(snap)
    assert not report.ok
    assert any("ghost" in e for e in report.errors)


def test_bad_evidence_value_errors():
    snap = _minimal_snapshot()
    snap.entities.tracks[0].evidence = "made_up"
    report = validate_snapshot(snap)
    assert not report.ok
    assert any("evidence" in e for e in report.errors)


def test_duplicate_entity_id_errors():
    snap = _minimal_snapshot()
    snap.entities.channels.append(S.CanonicalEntity(id="tr_1", kind="channel"))
    report = validate_snapshot(snap)
    assert not report.ok
    assert any("Duplicate" in e for e in report.errors)


def test_version_gate():
    assert is_compatible("0.2.0")
    assert is_compatible("0.2.5")   # same major.minor
    assert not is_compatible("1.0.0")
    assert not is_compatible("0.1.0")
    snap = _minimal_snapshot()
    snap.schema_version = "1.0.0"
    report = validate_snapshot(snap)
    assert not report.ok
    assert any("Incompatible" in e for e in report.errors)


def test_migrate_rejects_incompatible():
    import pytest
    assert migrate_snapshot({"schema_version": "0.2.0"}) == {"schema_version": "0.2.0"}
    with pytest.raises(ValueError):
        migrate_snapshot({"schema_version": "2.0.0"})


def test_entities_all_collects_every_list():
    snap = _minimal_snapshot()
    kinds = {e.kind for e in snap.entities.all()}
    assert {"track", "channel", "hidden_state"} <= kinds
