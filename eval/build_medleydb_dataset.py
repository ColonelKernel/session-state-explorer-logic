"""Build the MedleyDB instrument-vocabulary benchmark CSV.

MedleyDB (Bittner et al., 2014) ships per-track metadata with curated
instrument labels — realistic vocabulary for what producers type as track
names. This script aggregates those labels and attaches the *expected* role
under this prototype's taxonomy, producing
``data/eval/medleydb_instruments.csv``.

Ground-truth policy:

- Labels squarely inside a taxonomy category map to it.
- Labels the taxonomy has no bucket for (woodwinds, pitched mallets, many
  non-Western instruments) map to ``Unknown``: for those the *correct*
  behaviour of a filename classifier with this taxonomy is abstention.
  They are tagged ``out_of_taxonomy`` so metrics can be split.
- Non-instrument labels (room mics, unlabeled) are excluded.

Usage:
    python eval/build_medleydb_dataset.py path/to/medleydb/data/Metadata

Requires a checkout of https://github.com/marl/medleydb (metadata only; a
blob-less sparse clone is enough). The output CSV is committed so the
benchmark itself runs without the clone.
"""

from __future__ import annotations

import collections
import csv
import glob
import os
import re
import sys

ROLE_MAPPING: dict[str, str] = {
    # Drums / percussion
    "drum set": "Drums", "snare drum": "Drums", "kick drum": "Drums",
    "bass drum": "Drums", "toms": "Drums", "high hat": "Drums",
    "cymbal": "Drums", "drum machine": "Drums", "auxiliary percussion": "Drums",
    "tabla": "Drums", "tambourine": "Drums", "bongo": "Drums",
    "cabasa": "Drums", "castanet": "Drums", "claps": "Drums",
    "cowbell": "Drums", "darbuka": "Drums", "doumbek": "Drums",
    "gong": "Drums", "guiro": "Drums", "shaker": "Drums",
    "sleigh bells": "Drums", "timpani": "Drums", "chimes": "Drums",
    # Bass
    "electric bass": "Bass", "double bass": "Bass",
    # Guitar
    "acoustic guitar": "Guitar", "clean electric guitar": "Guitar",
    "distorted electric guitar": "Guitar", "lap steel guitar": "Guitar",
    # Vocal
    "male singer": "Vocal", "female singer": "Vocal", "vocalists": "Vocal",
    "male rapper": "Vocal", "male screamer": "Vocal", "male speaker": "Vocal",
    # Keys
    "piano": "Keys", "electric piano": "Keys", "tack piano": "Keys",
    "synthesizer": "Keys", "electronic organ": "Keys",
    # Strings
    "violin": "Strings", "viola": "Strings", "cello": "Strings",
    "violin section": "Strings", "viola section": "Strings",
    "cello section": "Strings", "string section": "Strings",
    # Brass
    "brass section": "Brass", "trumpet": "Brass", "trumpet section": "Brass",
    "trombone": "Brass", "trombone section": "Brass", "french horn": "Brass",
    "french horn section": "Brass", "tuba": "Brass", "cornet": "Brass",
    "euphonium": "Brass", "horn section": "Brass",
    # FX
    "fx/processed sound": "FX", "scratches": "FX",
}

# The taxonomy has no bucket for these; correct behaviour is abstention.
# "sampler" is deliberately here rather than FX: a sampler stem can be drums,
# keys, or chops, so mapping it into any single role would be arbitrary (and
# pairing a keyword with a chosen ground truth would be self-confirming).
OUT_OF_TAXONOMY = {
    "sampler",
    "alto saxophone", "tenor saxophone", "soprano saxophone",
    "baritone saxophone", "clarinet", "clarinet section", "bass clarinet",
    "flute", "flute section", "piccolo", "bamboo flute", "dizi", "oboe",
    "bassoon", "harmonica", "melodica", "accordion", "banjo", "mandolin",
    "harp", "oud", "sitar", "erhu", "gu", "guzheng", "liuqin", "yangqin",
    "zhongruan", "dilruba", "whistle", "vibraphone", "glockenspiel",
}

# Not instrument labels at all.
EXCLUDED = {"Main System", "Unlabeled", "crowd"}


def collect_labels(metadata_dir: str) -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    pattern = os.path.join(metadata_dir, "*.yaml")
    for path in glob.glob(pattern):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"\s+instrument:\s*(.+)\s*$", line)
                if m:
                    label = m.group(1).strip().strip("'\"")
                    if label and not label.startswith("["):
                        counts[label] += 1
    return counts


def main(metadata_dir: str, out_path: str = "data/eval/medleydb_instruments.csv") -> int:
    counts = collect_labels(metadata_dir)
    if not counts:
        print(f"No metadata found under {metadata_dir}", file=sys.stderr)
        return 2

    rows = []
    unmapped = []
    for label, count in sorted(counts.items()):
        if label in EXCLUDED:
            continue
        if label in ROLE_MAPPING:
            rows.append((label, ROLE_MAPPING[label], count, "in_taxonomy"))
        elif label in OUT_OF_TAXONOMY:
            rows.append((label, "Unknown", count, "out_of_taxonomy"))
        else:
            unmapped.append(label)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["name", "expected_role", "count", "category"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} labels ({sum(c for _l, _r, c, _g in rows)} instances) to {out_path}")
    if unmapped:
        print(f"Unmapped labels (excluded): {', '.join(unmapped)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
