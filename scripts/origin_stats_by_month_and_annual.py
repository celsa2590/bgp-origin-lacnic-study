#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from collections import Counter, defaultdict

ORIGINS = ("IGP", "INCOMPLETE", "EGP")

def detect_format_and_origin(fields):
    """
    Soporta 2 formatos:
    A) bgpdump TABLE_DUMP2:
       TABLE_DUMP2|...|prefix|as_path|ORIGIN|next_hop|...
       -> ORIGIN está típicamente en fields[7]
    B) formato compacto:
       prefix|CC|ORIGIN|origin_asn|peer_ip|peer_asn|next_hop|as_path|timestamp
       -> ORIGIN está en fields[2]
    """
    if not fields:
        return None

    # Formato A: TABLE_DUMP2
    if fields[0] == "TABLE_DUMP2":
        # necesitamos al menos hasta ORIGIN (índice 7)
        if len(fields) > 7:
            origin = fields[7].strip().upper()
            return origin if origin in ORIGINS else None
        return None

    # Formato B: compacto (ORIGIN en pos 2)
    if len(fields) >= 3:
        origin = fields[2].strip().upper()
        return origin if origin in ORIGINS else None

    return None


def month_from_filename(path):
    """
    Extrae YYMM o YYYYMM desde nombres tipo:
      ribpe_2501.txt.lacnic.v4.txt
      ribcl_2409.txt.lacnic.v6.txt
      rib.20231101.0000... -> también soportable si aparece YYYYMM
    """
    base = os.path.basename(path)

    m = re.search(r'_(\d{2})(\d{2})\b', base)  # _2501
    if m:
        yy, mm = m.group(1), m.group(2)
        return f"20{yy}{mm}"

    m = re.search(r'(\d{6})', base)  # YYYYMM
    if m:
        return m.group(1)

    # fallback
    return "UNKNOWN"


def summarize_counts(counter: Counter):
    total = sum(counter.values())
    out = {}
    for k in ORIGINS:
        out[k] = counter.get(k, 0)
    out["TOTAL"] = total
    return out


def pct(part, total):
    return 0.0 if total == 0 else (100.0 * part / total)


def write_monthly_report(path, monthly_rows):
    # monthly_rows: list of (month, totals_dict)
    with open(path, "w", encoding="utf-8") as f:
        f.write("📊 Resumen atributo BGP ORIGIN (LACNIC) - Por mes\n\n")
        f.write("Mes     - Total      - INCOMPLETE   - %INCOMPLETE - IGP         - %IGP       - EGP - %EGP\n")
        f.write("-----------------------------------------------------------------------------------------\n")
        for month, d in monthly_rows:
            total = d["TOTAL"]
            inc = d["INCOMPLETE"]
            igp = d["IGP"]
            egp = d["EGP"]
            f.write(
                f"{month} - "
                f"{total:10d} - "
                f"{inc:11d} - {pct(inc,total):10.2f}% - "
                f"{igp:10d} - {pct(igp,total):9.2f}% - "
                f"{egp:3d} - {pct(egp,total):6.2f}%\n"
            )


def write_annual_report(path, annual_counter: Counter, mode="sum"):
    """
    mode:
      - sum: suma de rutas/entradas en todos los meses
      - avg: promedio mensual (útil si quieres evitar que 'anual' parezca una suma)
    """
    total = sum(annual_counter.values())
    igp = annual_counter.get("IGP", 0)
    inc = annual_counter.get("INCOMPLETE", 0)
    egp = annual_counter.get("EGP", 0)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 Resumen atributo BGP ORIGIN (LACNIC) - Anual ({mode})\n\n")
        f.write("ORIGIN       - Cantidad   - Porcentaje\n")
        f.write("--------------------------------------\n")
        f.write(f"IGP          - {igp:9d} - {pct(igp,total):9.2f}%\n")
        f.write(f"INCOMPLETE   - {inc:9d} - {pct(inc,total):9.2f}%\n")
        f.write(f"EGP          - {egp:9d} - {pct(egp,total):9.2f}%\n\n")
        f.write(f"Total prefijos/entradas analizados: {total}\n")


def main():
    ap = argparse.ArgumentParser(
        description="Estadísticas ORIGIN por mes y anual desde archivos lacnic txt (v4/v6)."
    )
    ap.add_argument("--in-dir", required=True, help="Directorio con archivos *.lacnic.v4.txt o *.lacnic.v6.txt")
    ap.add_argument("--only", choices=["v4", "v6"], required=True, help="Procesar solo v4 o solo v6")
    ap.add_argument("--out-dir", required=True, help="Directorio de salida para reportes")
    ap.add_argument("--collector", default="COLECTOR", help="Etiqueta del colector (PE/CL/MX/BR_RIO/...)")
    ap.add_argument("--annual-mode", choices=["sum", "avg"], default="sum",
                    help="sum = suma de entradas; avg = promedio mensual (requiere 12 meses o los que haya)")
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

    monthly = defaultdict(Counter)

    for path in files:
        month = month_from_filename(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                fields = line.split("|")
                origin = detect_format_and_origin(fields)
                if origin:
                    monthly[month][origin] += 1

    # Ordenar meses
    months_sorted = sorted(monthly.keys())
    monthly_rows = [(m, summarize_counts(monthly[m])) for m in months_sorted]

    # Anual
    annual_counter = Counter()
    if args.annual_mode == "sum":
        for m in months_sorted:
            annual_counter.update(monthly[m])
    else:
        # promedio mensual: sum / N meses (redondeo al entero más cercano)
        n = len(months_sorted)
        sums = Counter()
        for m in months_sorted:
            sums.update(monthly[m])
        for k in ORIGINS:
            annual_counter[k] = int(round(sums.get(k, 0) / n))

    # Output
    monthly_out = os.path.join(out_dir, f"origin_monthly_{args.collector}_{args.only}.txt")
    annual_out = os.path.join(out_dir, f"origin_annual_{args.collector}_{args.only}_{args.annual_mode}.txt")

    write_monthly_report(monthly_out, monthly_rows)
    write_annual_report(annual_out, annual_counter, mode=args.annual_mode)

    print(f"✅ Mensual: {monthly_out}")
    print(f"✅ Anual:   {annual_out}")
    print(f"ℹ️ Archivos procesados: {len(files)} ({args.only})")


if __name__ == "__main__":
    main()
