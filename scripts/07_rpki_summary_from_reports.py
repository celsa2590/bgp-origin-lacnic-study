#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
from collections import defaultdict

ORIGIN_BUCKETS = ["IGP", "INCOMPLETE", "EGP", "MIXED"]
RPKI_BUCKETS = ["valid", "invalid", "not_found"]


def parse_count_pct_line(line: str):
    """
    Ejemplo:
    IGP         :  1405888 ( 86.77%)
    valid       :   972519 ( 60.02%)
    """
    m = re.match(r'^\s*([A-Za-z_+]+)\s*:\s*([\d]+)\s*\(\s*([\d.]+)%\s*\)\s*$', line)
    if not m:
        return None
    label = m.group(1)
    count = int(m.group(2))
    pct = float(m.group(3))
    return label, count, pct


def parse_cross_line(line: str):
    """
    Ejemplo:
    IGP          | 826163 |  58.76% |    2197 |     0.16% |    577528 |      41.08%
    """
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 7:
        return None

    label = parts[0]
    if label not in ORIGIN_BUCKETS:
        return None

    try:
        return {
            "origin": label,
            "valid_count": int(parts[1]),
            "valid_pct": float(parts[2].replace("%", "").strip()),
            "invalid_count": int(parts[3]),
            "invalid_pct": float(parts[4].replace("%", "").strip()),
            "not_found_count": int(parts[5]),
            "not_found_pct": float(parts[6].replace("%", "").strip()),
        }
    except ValueError:
        return None


def parse_report(path: str):
    data = {
        "title": "",
        "total": None,
        "origin_dist": {},
        "rpki_dist": {},
        "cross": {},
        "mixed": {},
    }

    section = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")

            if not data["title"] and line.startswith("📊"):
                data["title"] = line.strip()
                continue

            m_total = re.match(r"^Total prefijos analizados:\s+(\d+)\s*$", line)
            if m_total:
                data["total"] = int(m_total.group(1))
                continue

            if line.startswith("Distribución ORIGIN"):
                section = "origin"
                continue
            if line.startswith("Distribución RPKI"):
                section = "rpki"
                continue
            if line.startswith("Cruce ORIGIN × RPKI"):
                section = "cross"
                continue
            if line.startswith("Desglose MIXED"):
                section = "mixed"
                continue

            if not line.strip():
                continue
            if set(line.strip()) == {"-"}:
                continue
            if line.startswith("Unidad analítica:") or line.startswith("ORIGIN:") or line.startswith("RPKI:"):
                continue
            if line.startswith("ORIGIN       |"):
                continue

            if section == "origin":
                parsed = parse_count_pct_line(line)
                if parsed and parsed[0] in ORIGIN_BUCKETS:
                    label, count, pct = parsed
                    data["origin_dist"][label] = {"count": count, "pct": pct}
                continue

            if section == "rpki":
                parsed = parse_count_pct_line(line)
                if parsed and parsed[0] in RPKI_BUCKETS:
                    label, count, pct = parsed
                    data["rpki_dist"][label] = {"count": count, "pct": pct}
                continue

            if section == "cross":
                parsed = parse_cross_line(line)
                if parsed:
                    data["cross"][parsed["origin"]] = parsed
                continue

            if section == "mixed":
                parsed = parse_count_pct_line(line)
                if parsed:
                    label, count, pct = parsed
                    data["mixed"][label] = {"count": count, "pct": pct}
                continue

    return data


def infer_collector(path: str):
    """
    Intenta inferir colector desde el path:
    stats/rpki/v4_CL/rpki_correlation_v4.txt
    """
    norm = path.replace("\\", "/")
    m = re.search(r'/v[46]_([^/]+)/rpki_correlation_v[46](?:_\d{6})?\.txt$', norm)
    if m:
        return m.group(1)
    return os.path.basename(os.path.dirname(path))


def write_summary(output_path: str, reports: dict):
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("📊 Resumen general ORIGIN × RPKI por colector\n\n")

        out.write("Tabla base por colector\n")
        out.write("----------------------\n")
        out.write(
            "Colector | Total | %IGP | %INCOMPLETE | %EGP | %MIXED | %valid | %invalid | %not_found\n"
        )
        out.write(
            "----------------------------------------------------------------------------------------\n"
        )

        collectors_sorted = sorted(
            reports.keys(),
            key=lambda c: reports[c].get("total", 0),
            reverse=True
        )

        for c in collectors_sorted:
            r = reports[c]
            total = r.get("total", 0)
            od = r.get("origin_dist", {})
            rd = r.get("rpki_dist", {})

            out.write(
                f"{c:8s} | "
                f"{total:5d} | "
                f"{od.get('IGP', {}).get('pct', 0):5.2f}% | "
                f"{od.get('INCOMPLETE', {}).get('pct', 0):12.2f}% | "
                f"{od.get('EGP', {}).get('pct', 0):5.2f}% | "
                f"{od.get('MIXED', {}).get('pct', 0):7.2f}% | "
                f"{rd.get('valid', {}).get('pct', 0):6.2f}% | "
                f"{rd.get('invalid', {}).get('pct', 0):8.2f}% | "
                f"{rd.get('not_found', {}).get('pct', 0):10.2f}%\n"
            )

        out.write("\nCruce resumido ORIGIN × RPKI por colector\n")
        out.write("----------------------------------------\n")

        for c in collectors_sorted:
            r = reports[c]
            out.write(f"\n[{c}]\n")
            cross = r.get("cross", {})
            for origin in ORIGIN_BUCKETS:
                row = cross.get(origin)
                if not row:
                    continue
                out.write(
                    f"{origin:12s} -> "
                    f"valid: {row['valid_pct']:.2f}% | "
                    f"invalid: {row['invalid_pct']:.2f}% | "
                    f"not_found: {row['not_found_pct']:.2f}%\n"
                )

        out.write("\nRanking por %valid\n")
        out.write("------------------\n")
        for i, (c, r) in enumerate(
            sorted(reports.items(), key=lambda x: x[1].get("rpki_dist", {}).get("valid", {}).get("pct", 0), reverse=True),
            1
        ):
            out.write(f"{i:02d}. {c}: {r.get('rpki_dist', {}).get('valid', {}).get('pct', 0):.2f}%\n")

        out.write("\nRanking por %MIXED\n")
        out.write("------------------\n")
        for i, (c, r) in enumerate(
            sorted(reports.items(), key=lambda x: x[1].get("origin_dist", {}).get("MIXED", {}).get("pct", 0), reverse=True),
            1
        ):
            out.write(f"{i:02d}. {c}: {r.get('origin_dist', {}).get('MIXED', {}).get('pct', 0):.2f}%\n")


def main():
    ap = argparse.ArgumentParser(description="Resume reportes ORIGIN × RPKI generados por colector.")
    ap.add_argument("--reports", nargs="+", required=True, help="Lista de reportes anuales rpki_correlation_v4.txt o v6.txt")
    ap.add_argument("--out", required=True, help="Archivo de salida resumen")
    args = ap.parse_args()

    reports = {}
    for path in args.reports:
        collector = infer_collector(path)
        reports[collector] = parse_report(path)

    write_summary(args.out, reports)
    print(f"✅ {args.out}")


if __name__ == "__main__":
    main()
