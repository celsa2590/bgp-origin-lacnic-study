#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
03_origin_monthly_annual.py

Calcula estadísticas mensuales y anuales del atributo BGP ORIGIN
a partir de archivos compactos LACNIC, contando PREFIJOS ÚNICOS
(no líneas).

Formato de entrada esperado:
prefix|cc|origin|origin_asn|origin_asn_type|peer_ip|peer_asn|next_hop|as_path|timestamp|collector

Clasificación por prefijo dentro de cada mes:
- IGP
- EGP
- INCOMPLETE
- MIXED  (si el mismo prefijo aparece con más de un ORIGIN)

Además genera desglose interno de MIXED por firma:
- EGP+IGP
- EGP+INCOMPLETE
- IGP+INCOMPLETE
- EGP+IGP+INCOMPLETE
"""

import argparse
import os
import re
from collections import Counter, defaultdict

VALID_ORIGINS = {"IGP", "EGP", "INCOMPLETE"}
PRIMARY_BUCKETS = ("IGP", "INCOMPLETE", "EGP", "MIXED")


def month_from_filename(path: str) -> str:
    """
    Extrae YYYYMM desde nombres tipo:
      CL_20250101_0000.lacnic.v4.txt -> 202501
      ribcl_2501.txt.lacnic.v4.txt   -> 202501
      algo_202501.lacnic.v6.txt      -> 202501
    """
    base = os.path.basename(path)

    m = re.search(r'(\d{8})[_-]?(\d{4})', base)
    if m:
        ymd = m.group(1)
        return ymd[:6]

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
    """
    Devuelve:
      category: IGP / EGP / INCOMPLETE / MIXED
      mixed_signature: None si no es mixed, o firma ordenada tipo EGP+IGP
    """
    clean = {o for o in origins_seen if o in VALID_ORIGINS}

    if not clean:
        return "UNKNOWN", None

    if len(clean) == 1:
        return next(iter(clean)), None

    signature = "+".join(sorted(clean))
    return "MIXED", signature


def read_month_file(path: str) -> tuple[Counter, Counter, int, int]:
    """
    Lee un archivo mensual y devuelve:
      monthly_counts: Counter de categorías principales por prefijo único
      mixed_breakdown: Counter de firmas MIXED
      total_prefixes: cantidad total de prefijos únicos clasificados
      discarded_lines: líneas descartadas por formato/origin inválido
    """
    prefix_to_origins = defaultdict(set)
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
            origin = parts[2].strip().upper()

            if not prefix or origin not in VALID_ORIGINS:
                discarded += 1
                continue

            prefix_to_origins[prefix].add(origin)

    counts = Counter()
    mixed_breakdown = Counter()

    for prefix, origins in prefix_to_origins.items():
        category, signature = classify_prefix(origins)
        if category == "UNKNOWN":
            continue
        counts[category] += 1
        if category == "MIXED" and signature:
            mixed_breakdown[signature] += 1

    total_prefixes = sum(counts.values())
    return counts, mixed_breakdown, total_prefixes, discarded


def write_monthly_report(path: str, monthly_rows: list[dict], collector: str, only: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 Resumen ORIGIN por mes - {collector} - {only}\n\n")
        f.write("Unidad analítica: prefijos únicos por mes\n")
        f.write("Categorías: IGP, INCOMPLETE, EGP, MIXED\n\n")

        header = (
            "Mes     | Total | IGP | %IGP | INCOMPLETE | %INCOMPLETE | "
            "EGP | %EGP | MIXED | %MIXED | descartadas"
        )
        f.write(header + "\n")
        f.write("-" * len(header) + "\n")

        for row in monthly_rows:
            month = row["month"]
            total = row["total"]
            c = row["counts"]
            discarded = row["discarded"]

            igp = c.get("IGP", 0)
            inc = c.get("INCOMPLETE", 0)
            egp = c.get("EGP", 0)
            mixed = c.get("MIXED", 0)

            f.write(
                f"{month} | "
                f"{total:5d} | "
                f"{igp:3d} | {pct(igp,total):5.2f}% | "
                f"{inc:10d} | {pct(inc,total):11.2f}% | "
                f"{egp:3d} | {pct(egp,total):5.2f}% | "
                f"{mixed:5d} | {pct(mixed,total):7.2f}% | "
                f"{discarded}\n"
            )

            if row["mixed_breakdown"]:
                f.write("        MIXED breakdown:\n")
                for sig, n in sorted(row["mixed_breakdown"].items(), key=lambda x: (-x[1], x[0])):
                    f.write(f"          - {sig}: {n}\n")
                f.write("\n")


def write_annual_report_pooled(path: str, collector: str, only: str, annual_counts: Counter, annual_mixed: Counter):
    total = sum(annual_counts.values())

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 Resumen ORIGIN anual (pooled) - {collector} - {only}\n\n")
        f.write("Unidad analítica: prefijos únicos agregados por mes y luego sumados por categoría\n")
        f.write("Nota: este modo suma los conteos mensuales por categoría; no deduplica un prefijo entre meses.\n\n")

        f.write("Categoría    | Cantidad | Porcentaje\n")
        f.write("-------------------------------------\n")
        for bucket in PRIMARY_BUCKETS:
            n = annual_counts.get(bucket, 0)
            f.write(f"{bucket:12s} | {n:8d} | {pct(n,total):9.2f}%\n")

        f.write(f"\nTotal anual agregado: {total}\n")

        if annual_mixed:
            f.write("\nMIXED breakdown anual\n")
            f.write("---------------------\n")
            for sig, n in sorted(annual_mixed.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"{sig}: {n}\n")


def write_annual_report_avg_monthly_pct(path: str, collector: str, only: str, monthly_rows: list[dict]):
    n_months = len(monthly_rows)

    avg_pct = {}
    for bucket in PRIMARY_BUCKETS:
        avg_pct[bucket] = 0.0

    mixed_avg = defaultdict(float)

    for row in monthly_rows:
        total = row["total"]
        counts = row["counts"]

        for bucket in PRIMARY_BUCKETS:
            avg_pct[bucket] += pct(counts.get(bucket, 0), total)

        mixed_total = counts.get("MIXED", 0)
        for sig, n in row["mixed_breakdown"].items():
            mixed_avg[sig] += pct(n, mixed_total) if mixed_total else 0.0

    for bucket in PRIMARY_BUCKETS:
        avg_pct[bucket] = avg_pct[bucket] / n_months if n_months else 0.0

    for sig in list(mixed_avg.keys()):
        mixed_avg[sig] = mixed_avg[sig] / n_months if n_months else 0.0

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 Resumen ORIGIN anual (avg_monthly_pct) - {collector} - {only}\n\n")
        f.write("Unidad analítica: promedio simple de porcentajes mensuales de prefijos únicos\n")
        f.write("Nota: cada mes pesa igual, independiente del volumen de prefijos observados.\n\n")

        f.write("Categoría    | Promedio % mensual\n")
        f.write("-------------------------------\n")
        for bucket in PRIMARY_BUCKETS:
            f.write(f"{bucket:12s} | {avg_pct[bucket]:17.2f}%\n")

        if mixed_avg:
            f.write("\nMIXED breakdown promedio mensual (% dentro de MIXED)\n")
            f.write("---------------------------------------------------\n")
            for sig, v in sorted(mixed_avg.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"{sig}: {v:.2f}%\n")


def main():
    ap = argparse.ArgumentParser(
        description="Estadísticas ORIGIN por mes y anual desde archivos compactos LACNIC, contando prefijos únicos."
    )
    ap.add_argument("--in-dir", required=True, help="Directorio con archivos *.lacnic.v4.txt o *.lacnic.v6.txt")
    ap.add_argument("--only", choices=["v4", "v6"], required=True, help="Procesar solo v4 o v6")
    ap.add_argument("--out-dir", required=True, help="Directorio de salida")
    ap.add_argument("--collector", default="COLECTOR", help="Etiqueta del colector")
    ap.add_argument(
        "--annual-mode",
        choices=["pooled", "avg_monthly_pct"],
        default="pooled",
        help="pooled = suma de conteos mensuales por categoría; avg_monthly_pct = promedio simple de porcentajes mensuales"
    )
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

    monthly_rows = []
    annual_counts = Counter()
    annual_mixed = Counter()

    for path in files:
        month = month_from_filename(path)
        counts, mixed_breakdown, total, discarded = read_month_file(path)

        row = {
            "month": month,
            "counts": counts,
            "mixed_breakdown": mixed_breakdown,
            "total": total,
            "discarded": discarded,
        }
        monthly_rows.append(row)

        annual_counts.update(counts)
        annual_mixed.update(mixed_breakdown)

    monthly_rows.sort(key=lambda r: r["month"])

    monthly_out = os.path.join(out_dir, f"origin_monthly_{args.collector}_{args.only}.txt")
    annual_out = os.path.join(out_dir, f"origin_annual_{args.collector}_{args.only}_{args.annual_mode}.txt")

    write_monthly_report(monthly_out, monthly_rows, args.collector, args.only)

    if args.annual_mode == "pooled":
        write_annual_report_pooled(annual_out, args.collector, args.only, annual_counts, annual_mixed)
    else:
        write_annual_report_avg_monthly_pct(annual_out, args.collector, args.only, monthly_rows)

    print(f"✅ Mensual: {monthly_out}")
    print(f"✅ Anual:   {annual_out}")
    print(f"ℹ️ Archivos procesados: {len(files)} ({args.only})")


if __name__ == "__main__":
    main()
