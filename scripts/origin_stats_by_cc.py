#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from collections import Counter, defaultdict

ORIGINS = ("IGP", "INCOMPLETE", "EGP")

def detect_format_origin_cc(fields):
    """
    Soporta:
    A) bgpdump TABLE_DUMP2:
       TABLE_DUMP2|...|peer_ip|peer_asn|prefix|as_path|ORIGIN|...
       -> CC NO viene en TABLE_DUMP2, así que en ese caso NO podemos sacar CC.
          (Este script asume que tus archivos lacnic por mes incluyen CC en columna 2,
           es decir el formato "compacto".)

    B) Formato compacto:
       prefix|CC|ORIGIN|origin_asn|peer_ip|peer_asn|next_hop|as_path|timestamp
       -> CC = fields[1], ORIGIN = fields[2]
    """
    if not fields:
        return None, None

    # Formato compacto esperado
    if fields[0] != "TABLE_DUMP2" and len(fields) >= 3:
        cc = fields[1].strip().upper()
        origin = fields[2].strip().upper()
        if origin not in ORIGINS:
            return None, None
        if not cc or len(cc) != 2:
            # algunos colectores podrían usar "RIS_UY" como etiqueta, pero CC debe ser 2 letras
            return None, None
        return cc, origin

    # Si llega TABLE_DUMP2 no hay CC => no se puede (a menos que lo mapees por prefijo->CC)
    return None, None


def month_from_filename(path):
    base = os.path.basename(path)
    m = re.search(r'_(\d{2})(\d{2})\b', base)  # _2501
    if m:
        yy, mm = m.group(1), m.group(2)
        return f"20{yy}{mm}"
    m = re.search(r'(\d{6})', base)  # YYYYMM
    if m:
        return m.group(1)
    return "UNKNOWN"


def pct(part, total):
    return 0.0 if total == 0 else (100.0 * part / total)


def fmt_cc_line(cc, counts: Counter):
    total = sum(counts.values())
    inc = counts.get("INCOMPLETE", 0)
    igp = counts.get("IGP", 0)
    egp = counts.get("EGP", 0)
    return (
        f"{cc} - "
        f"incomplete: {inc} ({pct(inc,total):.2f}%) - "
        f"igp: {igp} ({pct(igp,total):.2f}%) - "
        f"egp: {egp} ({pct(egp,total):.2f}%)"
    )


def main():
    ap = argparse.ArgumentParser(
        description="Estadísticas ORIGIN por país (CC) desde archivos lacnic.v4/v6 en formato compacto."
    )
    ap.add_argument("--in-dir", required=True, help="Directorio con archivos *.lacnic.v4.txt o *.lacnic.v6.txt")
    ap.add_argument("--only", choices=["v4", "v6"], required=True, help="Procesar solo v4 o solo v6")
    ap.add_argument("--out-dir", required=True, help="Directorio de salida")
    ap.add_argument("--collector", default="COLECTOR", help="Etiqueta del colector (PE/CL/MX/BR_RIO/...)")
    ap.add_argument("--scope", choices=["month", "all"], default="all",
                    help="month = generar un output por cada mes; all = un solo resumen global (todos los meses)")
    ap.add_argument("--top", type=int, default=10, help="Top N por porcentaje de INCOMPLETE (solo en resumen global)")
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

    # scope=all: acumula todos los meses
    if args.scope == "all":
        by_cc = defaultdict(Counter)

        invalid = 0
        for path in files:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    fields = line.split("|")
                    cc, origin = detect_format_origin_cc(fields)
                    if cc is None:
                        invalid += 1
                        continue
                    by_cc[cc][origin] += 1

        out_path = os.path.join(out_dir, f"origin_by_cc_{args.collector}_{args.only}.txt")
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(f"📊 ORIGIN por país (CC) - {args.collector} - {args.only} (todos los meses)\n\n")
            # ordenar por %INCOMPLETE desc, luego por total desc
            rows = []
            for cc, c in by_cc.items():
                total = sum(c.values())
                inc = c.get("INCOMPLETE", 0)
                rows.append((pct(inc,total), total, cc, c))
            rows.sort(reverse=True)

            for _, _, cc, c in rows:
                out.write(fmt_cc_line(cc, c) + "\n")

            # Top N por %INCOMPLETE
            out.write("\nTop por %INCOMPLETE\n")
            out.write("-------------------\n")
            for i, (pinc, total, cc, c) in enumerate(rows[:args.top], 1):
                out.write(f"{i:02d}. {cc} - %incomplete: {pinc:.2f}% - total: {total}\n")

            out.write(f"\nℹ️ líneas descartadas (sin CC/origin válido): {invalid}\n")

        print(f"✅ {out_path}")
        return

    # scope=month: genera un archivo por mes
    for path in files:
        month = month_from_filename(path)
        by_cc = defaultdict(Counter)
        invalid = 0

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                fields = line.split("|")
                cc, origin = detect_format_origin_cc(fields)
                if cc is None:
                    invalid += 1
                    continue
                by_cc[cc][origin] += 1

        out_path = os.path.join(out_dir, f"origin_by_cc_{args.collector}_{args.only}_{month}.txt")
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(f"📊 ORIGIN por país (CC) - {args.collector} - {args.only} - {month}\n\n")

            # ordenar por %INCOMPLETE desc, luego total desc
            rows = []
            for cc, c in by_cc.items():
                total = sum(c.values())
                inc = c.get("INCOMPLETE", 0)
                rows.append((pct(inc,total), total, cc, c))
            rows.sort(reverse=True)

            for _, _, cc, c in rows:
                out.write(fmt_cc_line(cc, c) + "\n")

            out.write(f"\nℹ️ líneas descartadas (sin CC/origin válido): {invalid}\n")

        print(f"✅ {out_path}")


if __name__ == "__main__":
    main()
