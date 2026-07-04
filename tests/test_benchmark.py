import csv
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "benchmark_role_inference", os.path.join(REPO, "eval", "benchmark_role_inference.py")
)
benchmark = importlib.util.module_from_spec(spec)
sys.modules["benchmark_role_inference"] = benchmark
spec.loader.exec_module(benchmark)


def _dataset(path):
    return os.path.join(REPO, "data", "eval", path)


def test_datasets_are_well_formed():
    for name in ("medleydb_instruments.csv", "curated_filenames.csv"):
        with open(_dataset(name), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert rows, name
        for row in rows:
            assert row["name"]
            assert row["expected_role"]
            assert int(row["count"]) >= 1


def test_benchmark_metrics_meet_reported_floor():
    rows = benchmark.load_rows([
        _dataset("medleydb_instruments.csv"), _dataset("curated_filenames.csv"),
    ])
    results = benchmark.evaluate(rows)
    # The committed evaluation doc reports 99.3%; fail loudly if a vocabulary
    # or matcher change regresses coverage below a conservative floor.
    assert results["accuracy"] >= 0.97
    assert results["by_category"]["curated"]["accuracy"] >= 0.95
    assert results["by_category"]["out_of_taxonomy"]["accuracy"] >= 0.95


def test_reliability_table_supports_confidence_constants():
    rows = benchmark.load_rows([
        _dataset("medleydb_instruments.csv"), _dataset("curated_filenames.csv"),
    ])
    results = benchmark.evaluate(rows)
    # Keyword-match confidences (>= 0.7) must be at least as accurate as the
    # confidence they claim — the constants are meant to be conservative.
    for entry in results["confidence_reliability"]:
        if entry["confidence"] >= 0.7 and entry["n"] >= 20:
            assert entry["observed_accuracy"] >= entry["confidence"]
