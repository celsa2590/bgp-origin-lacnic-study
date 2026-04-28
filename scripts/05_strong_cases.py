#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
05_strong_cases.py

Detecta "casos fuertes" de inconsistencia de ORIGIN entre colectores.

Definición:
  misma dupla (prefix, origin_asn) observada en 2 o más colectores,
  pero con más de un valor ORIGIN entre esos colectores.

Formato de entrada esperado:
prefix|cc|origin|origin_asn|origin_asn_type|peer_ip|peer_asn|next_hop|as_path|timestamp|collector

Notas:
- Solo considera origin_asn_type == "simple"
- Excluye origin_asn vacío
- Compara por mes (YYYYMM) usando todos los archivos encontrados
- Genera:
    1) detalle por caso fuerte
    2) resumen por mes
    3) top ASNs involucrados
    4) top países involucrados
    5) top colectores participantes
"""

import argparse
import os
import re
from collections import Counter, defaultdict

VALID_ORIGINS = {"IGP", "EGP", "INCOMPLETE"}


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


def safe_slug(text: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]+', '_', text)


def collect_input_files(in_dirs, only):
    suffix = f".lacnic.{only}.txt"
    files = []

    for in_dir in in_dirs:
        if not os.path.isdir(in_dir):
            continue

        for fn in os.listdir(in_dir):
            if fn.endswith(suffix):
                files.append(os.path.join(in_dir, fn))

    return sorted(files)


def load_month_data(files):
    """
    Devuelve:
      month_data[month][(prefix, origin_asn)] = {
          "cc": set(...),
          "origins": set(...),
          "collectors": set(...),
          "rows": [ {...}, ... ]
      }

    Cada row contiene:
      prefix, cc, origin, origin_asn, collector
    """
    month_data = defaultdict(lambda: defaultdict(lambda: {
        "cc": set(),
        "origins": set(),
        "collectors": set(),
        "rows": []
    }))

    discarded = 0

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
                origin_asn = parts[3].strip()
                origin_asn_type = parts[4].strip().lower()
                collector = parts[10].strip()

                if not prefix or origin not in VALID_ORIGINS:
                    discarded += 1
                    continue

                if not origin_asn or origin_asn_type != "simple":
                    continue

                key = (prefix, origin_asn)
                entry = month_data[month][key]

                entry["cc"].add(cc)
                entry["origins"].add(origin)
                entry["collectors"].add(collector)
                entry["rows"].append({
                    "prefix": prefix,
                    "cc": cc,
                    "origin": origin,
                    "origin_asn": origin_asn,
                    "collector": collector,
                })

    return month_data, discarded


def detect_strong_cases(month_map, min_collectors=2):
    """
    Un caso fuerte cumple:
      - misma dupla (prefix, origin_asn)
      - vista en al menos min_collectors colectores
      - con más de un ORIGIN entre esos colectores
    """
    strong_cases = []

    for (prefix, origin_asn), entry in month_map.items():
        if len(entry["collectors"]) < min_collectors:
            continue

        if len(entry["origins"]) <= 1:
            continue

        # resumir por colector -> origins vistos
        collector_to_origins = defaultdict(set)
        collector_to_cc = defaultdict(set)

        for row in entry["rows"]:
            collector_to_origins[row["collector"]].add(row["origin"])
            collector_to_cc[row["collector"]].add(row["cc"])

        strong_cases.append({
            "prefix": prefix,
            "origin_asn": origin_asn,
            "cc_set": set(entry["cc"]),
            "origins_seen": set(entry["origins"]),
            "collectors_seen": set(entry["collectors"]),
            "collector_to_origins": dict(collector_to_origins),
            "collector_to_cc": dict(collector_to_cc),
        })

    return strong_cases


def write_detail_report(path, month, strong_cases):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 Casos fuertes ORIGIN - detalle - {month}\n\n")
        f.write("Definición: misma dupla (prefix, origin_asn) con ORIGIN distinto entre colectores.\n")
        f.write("Filtro: origin_asn_type = simple\n\n")

        if not strong_cases:
            f.write("No se encontraron casos fuertes.\n")
            return

        for i, case in enumerate(
            sorted(
                strong_cases,
                key=lambda c: (
                    c["prefix"],
                    int(c["origin_asn"]) if c["origin_asn"].isdigit() else c["origin_asn"]
                )
            ),
            1
        ):
            prefix = case["prefix"]
            origin_asn = case["origin_asn"]
            cc_join = ",".join(sorted(case["cc_set"]))
            origins_join = ",".join(sorted(case["origins_seen"]))
            collectors_join = ",".join(sorted(case["collectors_seen"]))

            f.write(f"{i:04d}. prefix={prefix} | origin_asn={origin_asn} | cc={cc_join}\n")
            f.write(f"      origins_seen={origins_join}\n")
            f.write(f"      collectors_seen={collectors_join}\n")

            for collector in sorted(case["collector_to_origins"].keys()):
                origins = ",".join(sorted(case["collector_to_origins"][collector]))
                ccs = ",".join(sorted(case["collector_to_cc"][collector]))
                f.write(f"      - {collector}: origins={origins} cc={ccs}\n")

            f.write("\n")


def write_summary_report(path, month, strong_cases):
    total = len(strong_cases)

    by_signature = Counter()
    by_num_collectors = Counter()

    for case in strong_cases:
        signature = "+".join(sorted(case["origins_seen"]))
        by_signature[signature] += 1
        by_num_collectors[len(case["collectors_seen"])] += 1

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 Casos fuertes ORIGIN - resumen - {month}\n\n")
        f.write(f"Total casos fuertes: {total}\n\n")

        if total == 0:
            return

        f.write("Por firma de ORIGIN observado\n")
        f.write("-----------------------------\n")
        for sig, n in sorted(by_signature.items(), key=lambda x: (-x[1], x[0])):
            f.write(f"{sig}: {n} ({pct(n, total):.2f}%)\n")

        f.write("\nPor cantidad de colectores involucrados\n")
        f.write("---------------------------------------\n")
        for n_collectors, n_cases in sorted(by_num_collectors.items()):
            f.write(f"{n_collectors} colectores: {n_cases} ({pct(n_cases, total):.2f}%)\n")


def write_top_report(path, title, counter, total_cases, top):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{title}\n\n")

        if not counter:
            f.write("Sin datos.\n")
            return

        for i, (key, n) in enumerate(counter.most_common(top), 1):
            f.write(f"{i:02d}. {key}: {n} ({pct(n, total_cases):.2f}%)\n")


def build_top_counters(strong_cases):
    by_asn = Counter()
    by_cc = Counter()
    by_collector = Counter()

    for case in strong_cases:
        by_asn[case["origin_asn"]] += 1

        for cc in case["cc_set"]:
            by_cc[cc] += 1

        for collector in case["collectors_seen"]:
            by_collector[collector] += 1

    return by_asn, by_cc, by_collector


def write_global_summary(path, all_month_cases):
    total_cases = sum(len(v) for v in all_month_cases.values())
    month_counts = {month: len(cases) for month, cases in all_month_cases.items()}

    global_signature = Counter()
    global_asn = Counter()
    global_cc = Counter()
    global_collector = Counter()

    for month, cases in all_month_cases.items():
        by_asn, by_cc, by_collector = build_top_counters(cases)
        global_asn.update(by_asn)
        global_cc.update(by_cc)
        global_collector.update(by_collector)

        for case in cases:
            sig = "+".join(sorted(case["origins_seen"]))
            global_signature[sig] += 1

    with open(path, "w", encoding="utf-8") as f:
        f.write("📊 Casos fuertes ORIGIN - resumen global\n\n")
        f.write(f"Total casos fuertes: {total_cases}\n\n")

        f.write("Casos por mes\n")
        f.write("------------\n")
        for month in sorted(month_counts.keys()):
            n = month_counts[month]
            f.write(f"{month}: {n} ({pct(n, total_cases):.2f}%)\n")

        f.write("\nFirmas ORIGIN más frecuentes\n")
        f.write("----------------------------\n")
        for sig, n in global_signature.most_common(10):
            f.write(f"{sig}: {n} ({pct(n, total_cases):.2f}%)\n")

        f.write("\nTop origin ASNs\n")
        f.write("---------------\n")
        for asn, n in global_asn.most_common(10):
            f.write(f"{asn}: {n} ({pct(n, total_cases):.2f}%)\n")

        f.write("\nTop países (CC)\n")
        f.write("----------------\n")
        for cc, n in global_cc.most_common(10):
            f.write(f"{cc}: {n} ({pct(n, total_cases):.2f}%)\n")

        f.write("\nTop colectores involucrados\n")
        f.write("---------------------------\n")
        for collector, n in global_collector.most_common(10):
            f.write(f"{collector}: {n} ({pct(n, total_cases):.2f}%)\n")


def main():
    ap = argparse.ArgumentParser(
        description="Detecta casos fuertes de inconsistencia ORIGIN entre colectores."
    )
    ap.add_argument(
        "--in-dirs",
        required=True,
        nargs="+",
        help="Directorios de entrada con archivos compactos (*.lacnic.v4.txt o *.lacnic.v6.txt)"
    )
    ap.add_argument(
        "--only",
        required=True,
        choices=["v4", "v6"],
        help="Procesar solo v4 o v6"
    )
    ap.add_argument(
        "--out-dir",
        required=True,
        help="Directorio de salida"
    )
    ap.add_argument(
        "--min-collectors",
        type=int,
        default=2,
        help="Mínimo de colectores distintos para considerar un caso fuerte"
    )
    ap.add_argument(
        "--top",
        type=int,
        default=10,
        help="Top N para reportes de ASN/CC/colectores"
    )

    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    files = collect_input_files(args.in_dirs, args.only)
    if not files:
        raise SystemExit("No se encontraron archivos de entrada.")

    month_data, discarded = load_month_data(files)

    all_month_cases = {}

    for month in sorted(month_data.keys()):
        strong_cases = detect_strong_cases(month_data[month], min_collectors=args.min_collectors)
        all_month_cases[month] = strong_cases

        month_slug = safe_slug(month)

        detail_path = os.path.join(
            args.out_dir,
            f"strong_cases_detail_{args.only}_{month_slug}.txt"
        )
        summary_path = os.path.join(
            args.out_dir,
            f"strong_cases_summary_{args.only}_{month_slug}.txt"
        )
        top_asn_path = os.path.join(
            args.out_dir,
            f"strong_cases_top_asn_{args.only}_{month_slug}.txt"
        )
        top_cc_path = os.path.join(
            args.out_dir,
            f"strong_cases_top_cc_{args.only}_{month_slug}.txt"
        )
        top_collector_path = os.path.join(
            args.out_dir,
            f"strong_cases_top_collectors_{args.only}_{month_slug}.txt"
        )

        write_detail_report(detail_path, month, strong_cases)
        write_summary_report(summary_path, month, strong_cases)

        by_asn, by_cc, by_collector = build_top_counters(strong_cases)
        total_cases = len(strong_cases)

        write_top_report(
            top_asn_path,
            f"📊 Top origin ASNs en casos fuertes - {month}",
            by_asn,
            total_cases,
            args.top
        )
        write_top_report(
            top_cc_path,
            f"📊 Top países (CC) en casos fuertes - {month}",
            by_cc,
            total_cases,
            args.top
        )
        write_top_report(
            top_collector_path,
            f"📊 Top colectores involucrados en casos fuertes - {month}",
            by_collector,
            total_cases,
            args.top
        )

        print(f"✅ {summary_path}")
        print(f"✅ {detail_path}")

    global_summary_path = os.path.join(
        args.out_dir,
        f"strong_cases_global_summary_{args.only}.txt"
    )
    write_global_summary(global_summary_path, all_month_cases)

    print(f"✅ {global_summary_path}")
    print(f"ℹ️ líneas descartadas: {discarded}")


if __name__ == "__main__":
    main()
