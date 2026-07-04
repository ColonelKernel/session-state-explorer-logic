"""Benchmark filename role inference against labeled vocabularies.

Runs :func:`logic_session_evidence_explorer.role_inference.infer_role` over
one or more labeled CSVs (``name,expected_role,count,category``), weighting
each row by ``count``, and reports:

- accuracy, per-role precision / recall / F1;
- a confidence reliability table (per confidence bucket: mean confidence vs
  observed accuracy) — the calibration evidence for the hand-set constants;
- the most frequent confusions.

Results are written as JSON (``data/eval/results.json``) and as a Markdown
report (``docs/evaluation.md``).

Usage:
    PYTHONPATH=src python3 eval/benchmark_role_inference.py \
        data/eval/medleydb_instruments.csv data/eval/curated_filenames.csv
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from logic_session_evidence_explorer import role_inference  # noqa: E402


def load_rows(paths: list[str]) -> list[dict]:
    rows = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["count"] = int(row.get("count", 1))
                rows.append(row)
    return rows


def evaluate(rows: list[dict]) -> dict:
    per_role_tp: Counter = Counter()
    per_role_fp: Counter = Counter()
    per_role_fn: Counter = Counter()
    confusions: Counter = Counter()
    buckets: dict[float, list] = defaultdict(lambda: [0, 0])  # confidence -> [correct, total]
    total = correct = 0
    by_category: dict[str, list] = defaultdict(lambda: [0, 0])

    for row in rows:
        result = role_inference.infer_role(row["name"])
        expected, predicted, n = row["expected_role"], result.role, row["count"]
        total += n
        by_category[row.get("category", "all")][1] += n
        bucket = buckets[round(result.confidence, 2)]
        bucket[1] += n
        if predicted == expected:
            correct += n
            per_role_tp[expected] += n
            bucket[0] += n
            by_category[row.get("category", "all")][0] += n
        else:
            per_role_fp[predicted] += n
            per_role_fn[expected] += n
            confusions[(expected, predicted, row["name"])] += n

    roles = sorted(set(per_role_tp) | set(per_role_fp) | set(per_role_fn))
    per_role = {}
    for role in roles:
        tp, fp, fn = per_role_tp[role], per_role_fp[role], per_role_fn[role]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_role[role] = {
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3), "support": tp + fn,
        }

    reliability = [
        {"confidence": conf, "n": n, "observed_accuracy": round(c / n, 3)}
        for conf, (c, n) in sorted(buckets.items()) if n
    ]
    top_confusions = [
        {"expected": e, "predicted": p, "example": name, "count": n}
        for (e, p, name), n in confusions.most_common(12)
    ]
    categories = {
        cat: {"n": n, "accuracy": round(c / n, 3)}
        for cat, (c, n) in sorted(by_category.items()) if n
    }

    return {
        "total_instances": total,
        "accuracy": round(correct / total, 3) if total else None,
        "per_role": per_role,
        "by_category": categories,
        "confidence_reliability": reliability,
        "top_confusions": top_confusions,
    }


def to_markdown(results: dict, sources: list[str]) -> str:
    lines = [
        "# Role-inference evaluation",
        "",
        "Filename role inference benchmarked against labeled vocabularies "
        f"({', '.join(os.path.basename(s) for s in sources)}), weighted by "
        "instance count.",
        "",
        "- **MedleyDB instrument labels**: curated stem/raw instrument labels "
        "from the 330 multitracks in the current MedleyDB metadata (the 2014 "
        "release of Bittner et al. plus later additions) — realistic "
        "vocabulary for what producers type as track names. Labels the "
        "taxonomy has no bucket for (woodwinds, pitched mallets, samplers, "
        "several non-Western instruments) expect `Unknown`: correct behaviour "
        "there is *abstention*, reported separately below.",
        "- **Curated Logic-style filenames**: decorated export names "
        "(indices, `_Bounce`, `Stereo`, `Final`, camelCase) probing the "
        "filename-normalisation path. Synthetic but realistic; kept separate "
        "from the corpus-derived set.",
        "",
        f"**Overall accuracy: {results['accuracy']:.1%}** over "
        f"{results['total_instances']} weighted instances.",
        "",
        "| Group | Instances | Accuracy |",
        "| --- | --- | --- |",
    ]
    for cat, stats in results["by_category"].items():
        lines.append(f"| {cat} | {stats['n']} | {stats['accuracy']:.1%} |")

    lines += ["", "## Per-role precision / recall", "",
              "| Role | Precision | Recall | F1 | Support |", "| --- | --- | --- | --- | --- |"]
    for role, m in results["per_role"].items():
        lines.append(f"| {role} | {m['precision']:.2f} | {m['recall']:.2f} | "
                     f"{m['f1']:.2f} | {m['support']} |")

    lines += ["", "## Confidence reliability", "",
              "Observed accuracy per emitted confidence value. Perfectly "
              "calibrated confidences would match their observed accuracy.", "",
              "| Emitted confidence | n | Observed accuracy |", "| --- | --- | --- |"]
    for r in results["confidence_reliability"]:
        lines.append(f"| {r['confidence']:.2f} | {r['n']} | {r['observed_accuracy']:.1%} |")

    lines += ["", "## Most frequent confusions", "",
              "| Expected | Predicted | Example label | Count |", "| --- | --- | --- | --- |"]
    for c in results["top_confusions"]:
        lines.append(f"| {c['expected']} | {c['predicted']} | `{c['example']}` | {c['count']} |")

    lines += [
        "",
        "## Reading these numbers",
        "",
        "This evaluates *vocabulary coverage* of the keyword taxonomy against "
        "real instrument labels and realistic export names — not performance "
        "on any specific artist's naming habits. Two caveats matter. First, "
        "the corpus-derived keyword extensions were selected from misses on "
        "this same corpus, so the headline accuracy is an **in-sample** "
        "coverage figure, not held-out generalization; validating on an "
        "independent corpus (e.g. Cambridge-MT multitrack names) is the "
        "natural next step. Second, misses on out-of-taxonomy labels are the "
        "taxonomy abstaining, which is the designed behaviour, while misses "
        "inside the taxonomy (drum overheads, room mics, rare percussion) are "
        "kept as honest gaps rather than patched with over-broad keywords. "
        "Confidence constants are hand-set; the reliability table above is "
        "the evidence for whether they are honest, and is regenerated by "
        "`eval/benchmark_role_inference.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    sources = argv or [
        "data/eval/medleydb_instruments.csv",
        "data/eval/curated_filenames.csv",
    ]
    rows = load_rows(sources)
    results = evaluate(rows)
    os.makedirs("data/eval", exist_ok=True)
    with open("data/eval/results.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    with open("docs/evaluation.md", "w", encoding="utf-8") as fh:
        fh.write(to_markdown(results, sources))
    print(f"Accuracy {results['accuracy']:.1%} over {results['total_instances']} instances "
          f"({len(rows)} distinct labels).")
    for cat, stats in results["by_category"].items():
        print(f"  {cat}: {stats['accuracy']:.1%} (n={stats['n']})")
    print("Wrote data/eval/results.json and docs/evaluation.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
