#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from collections import defaultdict, Counter

VALID_ORIGINS = {"IGP", "EGP", "INCOMPLETE"}
BUCKETS = ["IGP", "INCOMPLETE", "EGP", "MIXED"]

def month_from_filename(path):
    base = os.path.basename(path)

    m = re.search(r'(\d{8})[_-]?(\d{4})', base)
    if m:
        return m.group(1)[:6]

    m = re.search(r'_(\d{2})(\d{2})\b', base)
    if m:
        return f"20{m.group(1)}{m.group(2)}"

    m = re.search(r'(\d{6})', base)
    if m:
        return m.group(1)

    return "UNKNOWN"

def pct(n, total):
    return 0.0 if total == 0 else 100.0 * n / total

def classify(origins):
    origins = {o for o in origins if o in VALID_ORIGINS}
    if not origins:
        return None, None
    if len(origins) == 1:
        return next(iter(origins)), None
    return "MIXED", "+".join(sorted(origins))

def collect_files(in_dirs, only):
    suffix = f".lacnic.{only}.txt"
    files = []
    for d in in_dirs:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.endswith(suffix):
                files.append(os.path.join(d, fn))
    return sorted(files)

def main():
    ap = argparse.ArgumentParser(
        description="Calcula distribución ORIGIN por país usando archivos compactos LACNIC."
    )
    ap.add_argument("--in-dirs", nargs="+", required=True)
    ap.add_argument("--cc", required=True, help="Country code, ejemplo: PA")
    ap.add_argument("--only", choices=["v4", "v6"], required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    cc_filter = args.cc.upper()
    files = collect_files(args.in_dirs, args.only)

    if not files:
        raise SystemExit("No se encontraron archivos de entrada.")

    # data[collector][month][prefix] = set(origins)
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    discarded = 0
    matched_lines = 0

    for path in files:
        month = month_from_filename(path)

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) < 11:
                    discarded += 1
                    continue

                prefix = parts[0].strip()
                cc = parts[1].strip().upper()
                origin = parts[2].strip().upper()
                collector = parts[10].strip()

                if cc != cc_filter:
                    continue

                if not prefix or origin not in VALID_ORIGINS or not collector:
                    discarded += 1
                    continue

                data[collector][month][prefix].add(origin)
                matched_lines += 1

    monthly_csv = os.path.join(args.out_dir, f"origin_{cc_filter}_{args.only}_monthly.csv")
    summary_txt = os.path.join(args.out_dir, f"origin_{cc_filter}_{args.only}_summary.txt")

    with open(monthly_csv, "w", encoding="utf-8") as out:
        out.write(
            "collector,month,total_prefixes,igp,incomplete,egp,mixed,"
            "igp_pct,incomplete_pct,egp_pct,mixed_pct,"
            "mixed_egp_igp,mixed_egp_incomplete,mixed_igp_incomplete,mixed_egp_igp_incomplete\n"
        )

        summary = {}

        for collector in sorted(data.keys()):
            summary[collector] = Counter()
            summary_mixed = Counter()

            for month in sorted(data[collector].keys()):
                counts = Counter()
                mixed_breakdown = Counter()

                for prefix, origins in data[collector][month].items():
                    bucket, sig = classify(origins)
                    if not bucket:
                        continue
                    counts[bucket] += 1
                    if bucket == "MIXED":
                        mixed_breakdown[sig] += 1

                total = sum(counts.values())
                summary[collector].update(counts)
                summary_mixed.update(mixed_breakdown)

                out.write(
                    f"{collector},{month},{total},"
                    f"{counts['IGP']},{counts['INCOMPLETE']},{counts['EGP']},{counts['MIXED']},"
                    f"{pct(counts['IGP'], total):.2f},"
                    f"{pct(counts['INCOMPLETE'], total):.2f},"
                    f"{pct(counts['EGP'], total):.2f},"
                    f"{pct(counts['MIXED'], total):.2f},"
                    f"{mixed_breakdown.get('EGP+IGP', 0)},"
                    f"{mixed_breakdown.get('EGP+INCOMPLETE', 0)},"
                    f"{mixed_breakdown.get('IGP+INCOMPLETE', 0)},"
                    f"{mixed_breakdown.get('EGP+IGP+INCOMPLETE', 0)}\n"
                )

    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write(f"📊 ORIGIN para prefijos {cc_filter} - {args.only}\n\n")
        f.write("Unidad analítica: prefijos únicos por colector y mes\n\n")

        for collector in sorted(data.keys()):
            total_counts = Counter()
            total_mixed = Counter()

            for month in data[collector]:
                for prefix, origins in data[collector][month].items():
                    bucket, sig = classify(origins)
                    if not bucket:
                        continue
                    total_counts[bucket] += 1
                    if bucket == "MIXED":
                        total_mixed[sig] += 1

            total = sum(total_counts.values())

            f.write(f"{collector}\n")
            f.write("-" * len(collector) + "\n")
            f.write(f"Total prefijos-mes: {total}\n")
            for b in BUCKETS:
                f.write(f"{b:11s}: {total_counts[b]:8d} ({pct(total_counts[b], total):6.2f}%)\n")

            if total_mixed:
                f.write("MIXED breakdown:\n")
                for sig, n in total_mixed.most_common():
                    f.write(f"  - {sig}: {n}\n")
            f.write("\n")

    print(f"✅ CSV mensual: {monthly_csv}")
    print(f"✅ Resumen:     {summary_txt}")
    print(f"ℹ️ líneas PA encontradas: {matched_lines}")
    print(f"ℹ️ líneas descartadas: {discarded}")

if __name__ == "__main__":
    main()
