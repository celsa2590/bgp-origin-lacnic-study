#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import re
from collections import defaultdict, Counter

VALID_ORIGINS = {"IGP", "INCOMPLETE", "EGP"}

def extract_date(filename):
    m = re.search(r'(\d{8})', filename)
    return m.group(1) if m else None

def read_compact_file(filepath):
    prefix_origins = defaultdict(set)
    discarded = 0

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) < 3:
                discarded += 1
                continue

            prefix = parts[0].strip()
            origin = parts[2].strip().upper()

            if not prefix or origin not in VALID_ORIGINS:
                discarded += 1
                continue

            prefix_origins[prefix].add(origin)

    return prefix_origins, discarded

def classify(prefix_origins):
    counts = Counter({"IGP": 0, "INCOMPLETE": 0, "EGP": 0, "MIXED": 0})
    mixed_breakdown = Counter()

    for origins in prefix_origins.values():
        if len(origins) == 1:
            origin = next(iter(origins))
            counts[origin] += 1
        else:
            counts["MIXED"] += 1
            sig = "+".join(sorted(origins))
            mixed_breakdown[sig] += 1

    total = sum(counts.values())
    return counts, mixed_breakdown, total

def pct(n, total):
    return 0.0 if total == 0 else 100.0 * n / total

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", required=True)
    parser.add_argument("--collector", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--only", choices=["v4", "v6"], default="v4")
    args = parser.parse_args()

    suffix = f".lacnic.{args.only}.txt"
    files = sorted([f for f in os.listdir(args.in_dir) if f.endswith(suffix)])

    os.makedirs(os.path.dirname(args.out_file), exist_ok=True)

    with open(args.out_file, "w", encoding="utf-8") as out:
        out.write(
            "date,collector,afi,total,igp,incomplete,egp,mixed,"
            "igp_pct,incomplete_pct,egp_pct,mixed_pct,"
            "mixed_egp_igp,mixed_egp_incomplete,mixed_igp_incomplete,mixed_egp_igp_incomplete,discarded\n"
        )

        for filename in files:
            path = os.path.join(args.in_dir, filename)
            date = extract_date(filename)

            prefix_origins, discarded = read_compact_file(path)
            counts, mixed_breakdown, total = classify(prefix_origins)

            out.write(
                f"{date},{args.collector},{args.only},{total},"
                f"{counts['IGP']},{counts['INCOMPLETE']},{counts['EGP']},{counts['MIXED']},"
                f"{pct(counts['IGP'], total):.2f},"
                f"{pct(counts['INCOMPLETE'], total):.2f},"
                f"{pct(counts['EGP'], total):.2f},"
                f"{pct(counts['MIXED'], total):.2f},"
                f"{mixed_breakdown.get('EGP+IGP', 0)},"
                f"{mixed_breakdown.get('EGP+INCOMPLETE', 0)},"
                f"{mixed_breakdown.get('IGP+INCOMPLETE', 0)},"
                f"{mixed_breakdown.get('EGP+IGP+INCOMPLETE', 0)},"
                f"{discarded}\n"
            )

    print(f"✅ Daily summary generado: {args.out_file}")
    print(f"ℹ️ Archivos procesados: {len(files)} ({args.only})")

if __name__ == "__main__":
    main()
