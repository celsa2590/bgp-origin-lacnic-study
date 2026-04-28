#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
04_origin_by_cc.py

Calcula estadísticas ORIGIN por país (CC) a partir de archivos compactos LACNIC,
contando PREFIJOS ÚNICOS por país (no líneas).

Formato de entrada esperado:
prefix|cc|origin|origin_asn|origin_asn_type|peer_ip|peer_asn|next_hop|as_path|timestamp|collector

Clasificación por (cc, prefix):
- IGP
- EGP
- INCOMPLETE
- MIXED   (si el mismo prefijo aparece con más de un ORIGIN)

Soporta:
- scope=month : un archivo por mes
- scope=all   : un único resumen agregado sobre todos los meses
"""

import argparse
import os
import re
from collections import Counter, defaultdict

VALID_ORIGINS = {"IGP", "EGP", "INCOMPLETE"}
PRIMARY_BUCKETS = ("IGP", "INCOMPLETE", "EGP", "MIXED")
VALID_SORT_BY = {"pct_incomplete", "pct_egp", "pct_mixed", "total", "cc"}


def month_from_filename(path: str) -> str:
    base = os.path.basename(path)

    m = re.search(r'(\d{8})[_-]?(\d{4})', base)
    if m:
        return m.group(1)[:6]

    m = re.search(r'_(\d{2})(\d{2})\b', base)
    if m:
        yy, mm = m.group(1), m.group(2)
        return f"20{yy}{mm}"

    m = re.search(r'(\d{6})', base)
    if m:
        return m.group(1)

    return "UNKNOWN"


def pct(part: int, total: int) -> float:
    return 0.0 if total == 0 else (100.0 * part / total)


def classify_prefix(origins_seen: set[str]) -> tuple[str, str | None]:
    clean = {o for o in origins_seen if o in VALID_ORIGINS}

    if not clean:
        return "UNKNOWN", None

    if len(clean) == 1:
        return next(iter(clean)), None

    signature = "+".join(sorted(clean))
    return "MIXED", signature


def read_file_grouped_by_cc_prefix(path: str):
    """
    Lee un archivo y agrupa por (cc, prefix) -> set(origins)
    Devuelve:
      grouped: dict[cc][prefix] = set(origins)
      discarded: líneas descartadas
    """
    grouped = defaultdict(lambda: defaultdict(set))
    discarded = 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            parts = line.split("|")
            if len(parts) < 3:
                discarded += 1
                continue

            prefix = parts[0].strip()
            cc = parts[1].strip().upper()
            origin = parts[2].strip().upper()

            if not prefix or not cc or len(cc) != 2 or origin not in VALID_ORIGINS:
                discarded += 1
                continue

            grouped[cc][prefix].add(origin)

    return grouped, discarded


def summarize_grouped(grouped):
    """
    grouped: dict[cc][prefix] = set(origins)

    Devuelve:
      by_cc_counts: dict[cc] = Counter(IGP/INCOMPLETE/EGP/MIXED)
      by_cc_mixed: dict[cc] = Counter(firma_mixed)
      by_cc_total: dict[cc] = total prefijos únicos
    """
    by_cc_counts = {}
    by_cc_mixed = {}
    by_cc_total = {}

    for cc, prefixes in grouped.items():
        counts = Counter()
        mixed_breakdown = Counter()

        for prefix, origins in prefixes.items():
            category, signature = classify_prefix(origins)
            if category == "UNKNOWN":
                continue

            counts[category] += 1
            if category == "MIXED" and signature:
                mixed_breakdown[signature] += 1

        by_cc_counts[cc] = counts
        by_cc_mixed[cc] = mixed_breakdown
        by_cc_total[cc] = sum(counts.values())

    return by_cc_counts, by_cc_mixed, by_cc_total


def sort_rows(rows, sort_by):
    """
    rows: list of dict con campos:
      cc, total, pct_incomplete, pct_egp, pct_mixed
    """
    if sort_by == "pct_incomplete":
        return sorted(rows, key=lambda r: (-r["pct_incomplete"], -r["total"], r["cc"]))
    if sort_by == "pct_egp":
        return sorted(rows, key=lambda r: (-r["pct_egp"], -r["total"], r["cc"]))
    if sort_by == "pct_mixed":
        return sorted(rows, key=lambda r: (-r["pct_mixed"], -r["total"], r["cc"]))
    if sort_by == "total":
        return sorted(rows, key=lambda r: (-r["total"], r["cc"]))
    return sorted(rows, key=lambda r: r["cc"])


def build_rows(by_cc_counts, by_cc_mixed, by_cc_total, min_prefixes):
    rows = []

    for cc in sorted(by_cc_total.keys()):
        total = by_cc_total[cc]
        if total < min_prefixes:
            continue

        counts = by_cc_counts[cc]
        mixed_breakdown = by_cc_mixed[cc]

        igp = counts.get("IGP", 0)
        inc = counts.get("INCOMPLETE", 0)
        egp = counts.get("EGP", 0)
        mixed = counts.get("MIXED", 0)

        rows.append({
            "cc": cc,
            "counts": counts,
            "mixed_breakdown": mixed_breakdown,
            "total": total,
            "pct_igp": pct(igp, total),
            "pct_incomplete": pct(inc, total),
            "pct_egp": pct(egp, total),
            "pct_mixed": pct(mixed, total),
        })

    return rows


def write_cc_report(path, rows, collector, only, scope_label, discarded, top):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 ORIGIN por país (CC) - {collector} - {only} - {scope_label}\n\n")
        f.write("Unidad analítica: prefijos únicos por país (cc, prefix)\n")
        f.write("Categorías: IGP, INCOMPLETE, EGP, MIXED\n\n")

        if not rows:
            f.write("No hay resultados para los filtros aplicados.\n")
            f.write(f"\nℹ️ líneas descartadas: {discarded}\n")
            return

        header = (
            "CC | Total | IGP | %IGP | INCOMPLETE | %INCOMPLETE | "
            "EGP | %EGP | MIXED | %MIXED"
        )
        f.write(header + "\n")
        f.write("-" * len(header) + "\n")

        for row in rows[:top]:
            cc = row["cc"]
            total = row["total"]
            c = row["counts"]

            igp = c.get("IGP", 0)
            inc = c.get("INCOMPLETE", 0)
            egp = c.get("EGP", 0)
            mixed = c.get("MIXED", 0)

            f.write(
                f"{cc:2s} | "
                f"{total:5d} | "
                f"{igp:3d} | {pct(igp,total):5.2f}% | "
                f"{inc:10d} | {pct(inc,total):11.2f}% | "
                f"{egp:3d} | {pct(egp,total):5.2f}% | "
                f"{mixed:5d} | {pct(mixed,total):7.2f}%\n"
            )

            if row["mixed_breakdown"]:
                f.write("     MIXED breakdown:\n")
                for sig, n in sorted(row["mixed_breakdown"].items(), key=lambda x: (-x[1], x[0])):
                    f.write(f"       - {sig}: {n}\n")

        f.write(f"\nℹ️ líneas descartadas: {discarded}\n")
        f.write(f"ℹ️ países reportados: {min(top, len(rows))} de {len(rows)}\n")


def merge_grouped_dicts(base_grouped, new_grouped):
    """
    Fusiona:
      dict[cc][prefix] = set(origins)
    """
    for cc, prefixes in new_grouped.items():
        for prefix, origins in prefixes.items():
            base_grouped[cc][prefix].update(origins)


def main():
    ap = argparse.ArgumentParser(
        description="Estadísticas ORIGIN por país (CC), contando prefijos únicos."
    )
    ap.add_argument("--in-dir", required=True, help="Directorio con archivos *.lacnic.v4.txt o *.lacnic.v6.txt")
    ap.add_argument("--only", choices=["v4", "v6"], required=True, help="Procesar solo v4 o v6")
    ap.add_argument("--out-dir", required=True, help="Directorio de salida")
    ap.add_argument("--collector", default="COLECTOR", help="Etiqueta del colector")
    ap.add_argument("--scope", choices=["month", "all"], default="all",
                    help="month = un output por mes; all = un resumen único con todos los meses")
    ap.add_argument("--top", type=int, default=10, help="Top N países a mostrar en el reporte")
    ap.add_argument("--min-prefixes", type=int, default=1,
                    help="Mínimo de prefijos únicos por país para incluirlo")
    ap.add_argument("--sort-by", choices=sorted(VALID_SORT_BY), default="pct_incomplete",
                    help="Criterio de ordenamiento del ranking")

    args = ap.parse_args()

    in_dir = args.in_dir.rstrip("/")
    out_dir = args.out_dir.rstrip("/")
    os.makedirs(out_dir, exist_ok=True)

    suffix = f".lacnic.{args.only}.txt"
    files = sorted(
        os.path.join(in_dir, fn)
        for fn in os.listdir(in_dir)
        if fn.endswith(suffix)
    )

    if not files:
        raise SystemExit(f"No se encontraron archivos con sufijo {suffix} en {in_dir}")

    # ----------------------------
    # scope=all
    # ----------------------------
    if args.scope == "all":
        merged_grouped = defaultdict(lambda: defaultdict(set))
        discarded_total = 0

        for path in files:
            grouped, discarded = read_file_grouped_by_cc_prefix(path)
            merge_grouped_dicts(merged_grouped, grouped)
            discarded_total += discarded

        by_cc_counts, by_cc_mixed, by_cc_total = summarize_grouped(merged_grouped)
        rows = build_rows(by_cc_counts, by_cc_mixed, by_cc_total, args.min_prefixes)
        rows = sort_rows(rows, args.sort_by)

        out_path = os.path.join(out_dir, f"origin_by_cc_{args.collector}_{args.only}.txt")
        write_cc_report(
            out_path,
            rows,
            collector=args.collector,
            only=args.only,
            scope_label="all_months",
            discarded=discarded_total,
            top=args.top
        )
        print(f"✅ {out_path}")
        return

    # ----------------------------
    # scope=month
    # ----------------------------
    for path in files:
        month = month_from_filename(path)
        grouped, discarded = read_file_grouped_by_cc_prefix(path)
        by_cc_counts, by_cc_mixed, by_cc_total = summarize_grouped(grouped)
        rows = build_rows(by_cc_counts, by_cc_mixed, by_cc_total, args.min_prefixes)
        rows = sort_rows(rows, args.sort_by)

        out_path = os.path.join(out_dir, f"origin_by_cc_{args.collector}_{args.only}_{month}.txt")
        write_cc_report(
            out_path,
            rows,
            collector=args.collector,
            only=args.only,
            scope_label=month,
            discarded=discarded,
            top=args.top
        )
        print(f"✅ {out_path}")


if __name__ == "__main__":
    main()
