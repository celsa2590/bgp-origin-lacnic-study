#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
06_rpki_correlation.py

Cruza archivos compactos LACNIC con archivos ROA históricos mensuales
para analizar correlación entre:

- ORIGIN BGP (IGP / EGP / INCOMPLETE / MIXED)
- estado RPKI (valid / invalid / not_found)

Formato de entrada esperado (compact files):
prefix|cc|origin|origin_asn|origin_asn_type|peer_ip|peer_asn|next_hop|as_path|timestamp|collector

Formato esperado de ROAs mensuales:
URI,ASN,IP Prefix,Max Length,Not Before,Not After

Ejemplo:
roas_202501.csv
roas_202502.csv
...
"""

import argparse
import csv
import ipaddress
import os
import re
from collections import Counter, defaultdict

import pytricia

VALID_ORIGINS = {"IGP", "EGP", "INCOMPLETE"}
PRIMARY_BUCKETS = ("IGP", "INCOMPLETE", "EGP", "MIXED")
RPKI_STATES = ("valid", "invalid", "not_found")


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


def classify_origin_set(origins_seen: set[str]):
    clean = {o for o in origins_seen if o in VALID_ORIGINS}

    if not clean:
        return "UNKNOWN", None

    if len(clean) == 1:
        return next(iter(clean)), None

    signature = "+".join(sorted(clean))
    return "MIXED", signature


def normalize_asn(asn_value: str) -> str:
    x = asn_value.strip().upper()
    if x.startswith("AS"):
        x = x[2:]
    return x


class ROAIndex:
    """
    Índice eficiente de ROAs usando tries de prefijos.
    En cada prefijo ROA guardamos una lista de tuplas:
      (maxlen, asn)

    La validación busca solo las superredes candidatas del prefijo observado.
    """
    def __init__(self):
        self.v4 = pytricia.PyTricia(32)
        self.v6 = pytricia.PyTricia(128)

    def add(self, prefix: str, maxlen: int, asn: str):
        trie = self.v6 if ":" in prefix else self.v4
        key = prefix

        if key not in trie:
            trie[key] = []

        trie[key].append((maxlen, asn))

    def _candidate_entries(self, net):
        trie = self.v6 if net.version == 6 else self.v4

        candidates = []
        current = str(net)

        # Recorremos las superredes almacenadas que cubren al prefijo.
        # parent() en pytricia permite subir en el trie.
        try:
            if current in trie:
                k = current
            else:
                k = trie.get_key(str(net.network_address))
        except KeyError:
            k = None

        while k is not None:
            try:
                roa_net = ipaddress.ip_network(k, strict=False)
            except Exception:
                k = trie.parent(k) if k in trie else None
                continue

            if net.subnet_of(roa_net):
                entries = trie[k]
                for maxlen, asn in entries:
                    candidates.append((roa_net, maxlen, asn))

            try:
                k = trie.parent(k)
            except KeyError:
                k = None

        return candidates

    def validate(self, prefix: str, origin_asns: set[str]) -> str:
        try:
            net = ipaddress.ip_network(prefix, strict=False)
        except Exception:
            return "not_found"

        origin_asns = {normalize_asn(x) for x in origin_asns if x}

        covering = []
        for roa_net, maxlen, asn in self._candidate_entries(net):
            if net.prefixlen <= maxlen:
                covering.append((roa_net, maxlen, normalize_asn(asn)))

        if not covering:
            return "not_found"

        valid_asns = {asn for _, _, asn in covering}
        if origin_asns & valid_asns:
            return "valid"

        return "invalid"


def load_roas(roa_csv_path: str) -> ROAIndex:
    index = ROAIndex()

    with open(roa_csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV ROA vacío o sin cabecera: {roa_csv_path}")

        required = {"ASN", "IP Prefix", "Max Length"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Faltan columnas en {roa_csv_path}: {missing}")

        for row in reader:
            asn = normalize_asn(str(row.get("ASN", "")).strip())
            prefix = str(row.get("IP Prefix", "")).strip()
            maxlen_raw = str(row.get("Max Length", "")).strip()

            if not asn or not prefix or not maxlen_raw:
                continue

            try:
                net = ipaddress.ip_network(prefix, strict=False)
                maxlen = int(maxlen_raw)
            except Exception:
                continue

            if maxlen < net.prefixlen:
                continue

            index.add(str(net), maxlen, asn)

    return index


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


def load_compact_file_grouped(path):
    """
    Devuelve:
      prefix_map[prefix] = {
         "origins": set(),
         "origin_asns": set(),   # solo simple
         "cc": set(),
      }
    """
    prefix_map = defaultdict(lambda: {
        "origins": set(),
        "origin_asns": set(),
        "cc": set(),
    })

    discarded = 0

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

            if not prefix or origin not in VALID_ORIGINS:
                discarded += 1
                continue

            entry = prefix_map[prefix]
            entry["origins"].add(origin)
            entry["cc"].add(cc)

            if origin_asn and origin_asn_type == "simple":
                entry["origin_asns"].add(normalize_asn(origin_asn))

    return prefix_map, discarded


def summarize_prefix_map(prefix_map, roa_index: ROAIndex):
    by_origin = Counter()
    by_rpki = Counter()
    origin_x_rpki = defaultdict(Counter)
    mixed_breakdown = Counter()
    total = 0

    for prefix, info in prefix_map.items():
        origin_bucket, signature = classify_origin_set(info["origins"])
        if origin_bucket == "UNKNOWN":
            continue

        rpki_state = roa_index.validate(prefix, info["origin_asns"])

        total += 1
        by_origin[origin_bucket] += 1
        by_rpki[rpki_state] += 1
        origin_x_rpki[origin_bucket][rpki_state] += 1

        if origin_bucket == "MIXED" and signature:
            mixed_breakdown[signature] += 1

    return total, by_origin, by_rpki, origin_x_rpki, mixed_breakdown


def write_report(path, label, total, by_origin, by_rpki, origin_x_rpki, mixed_breakdown):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"📊 ORIGIN × RPKI - {label}\n\n")
        f.write("Unidad analítica: prefijos únicos\n")
        f.write("ORIGIN: IGP / INCOMPLETE / EGP / MIXED\n")
        f.write("RPKI: valid / invalid / not_found\n\n")

        f.write(f"Total prefijos analizados: {total}\n\n")

        f.write("Distribución ORIGIN\n")
        f.write("-------------------\n")
        for bucket in PRIMARY_BUCKETS:
            n = by_origin.get(bucket, 0)
            f.write(f"{bucket:12s}: {n:8d} ({pct(n,total):6.2f}%)\n")

        f.write("\nDistribución RPKI\n")
        f.write("-----------------\n")
        for state in RPKI_STATES:
            n = by_rpki.get(state, 0)
            f.write(f"{state:12s}: {n:8d} ({pct(n,total):6.2f}%)\n")

        f.write("\nCruce ORIGIN × RPKI\n")
        f.write("-------------------\n")
        header = "ORIGIN       | valid | %valid | invalid | %invalid | not_found | %not_found"
        f.write(header + "\n")
        f.write("-" * len(header) + "\n")

        for bucket in PRIMARY_BUCKETS:
            row_total = sum(origin_x_rpki[bucket].values())
            v = origin_x_rpki[bucket].get("valid", 0)
            i = origin_x_rpki[bucket].get("invalid", 0)
            n = origin_x_rpki[bucket].get("not_found", 0)

            f.write(
                f"{bucket:12s} | "
                f"{v:5d} | {pct(v,row_total):6.2f}% | "
                f"{i:7d} | {pct(i,row_total):8.2f}% | "
                f"{n:9d} | {pct(n,row_total):10.2f}%\n"
            )

        if mixed_breakdown:
            mixed_total = by_origin.get("MIXED", 0)
            f.write("\nDesglose MIXED\n")
            f.write("-------------\n")
            for sig, n in sorted(mixed_breakdown.items(), key=lambda x: (-x[1], x[0])):
                f.write(f"{sig}: {n} ({pct(n, mixed_total):.2f}% dentro de MIXED)\n")


def main():
    ap = argparse.ArgumentParser(
        description="Cruza ORIGIN con ROAs históricos mensuales."
    )
    ap.add_argument("--in-dirs", nargs="+", required=True,
                    help="Directorios con archivos compactos (*.lacnic.v4.txt o *.lacnic.v6.txt)")
    ap.add_argument("--only", choices=["v4", "v6"], required=True,
                    help="Procesar solo v4 o v6")
    ap.add_argument("--roa-dir", required=True,
                    help="Directorio con roas_YYYYMM.csv")
    ap.add_argument("--out-dir", required=True,
                    help="Directorio de salida")
    ap.add_argument("--scope", choices=["month", "all"], default="all",
                    help="month = un reporte por mes; all = mensual + resumen global agregado")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    files = collect_input_files(args.in_dirs, args.only)
    if not files:
        raise SystemExit("No se encontraron archivos compactos de entrada.")

    monthly_summaries = []
    total_discarded = 0

    for path in files:
        month = month_from_filename(path)
        roa_file = os.path.join(args.roa_dir, f"roas_{month}.csv")

        if not os.path.isfile(roa_file):
            print(f"⚠️ No existe ROA para {month}: {roa_file}. Saltando.")
            continue

        print(f"Procesando mes {month} con {os.path.basename(roa_file)}")

        prefix_map, discarded = load_compact_file_grouped(path)
        total_discarded += discarded

        roa_index = load_roas(roa_file)
        total, by_origin, by_rpki, origin_x_rpki, mixed_breakdown = summarize_prefix_map(prefix_map, roa_index)

        monthly_summaries.append({
            "month": month,
            "total": total,
            "by_origin": by_origin,
            "by_rpki": by_rpki,
            "origin_x_rpki": origin_x_rpki,
            "mixed_breakdown": mixed_breakdown,
        })

        if args.scope in ("month", "all"):
            out_path = os.path.join(args.out_dir, f"rpki_correlation_{args.only}_{month}.txt")
            write_report(
                out_path,
                f"{args.only} - {month}",
                total,
                by_origin,
                by_rpki,
                origin_x_rpki,
                mixed_breakdown
            )
            print(f"✅ {out_path}")

    if not monthly_summaries:
        raise SystemExit("No se pudo procesar ningún mes.")

    if args.scope == "all":
        total = sum(x["total"] for x in monthly_summaries)
        by_origin = Counter()
        by_rpki = Counter()
        origin_x_rpki = defaultdict(Counter)
        mixed_breakdown = Counter()

        for row in monthly_summaries:
            by_origin.update(row["by_origin"])
            by_rpki.update(row["by_rpki"])
            mixed_breakdown.update(row["mixed_breakdown"])
            for bucket, ctr in row["origin_x_rpki"].items():
                origin_x_rpki[bucket].update(ctr)

        out_path = os.path.join(args.out_dir, f"rpki_correlation_{args.only}.txt")
        write_report(
            out_path,
            f"{args.only} - all_months",
            total,
            by_origin,
            by_rpki,
            origin_x_rpki,
            mixed_breakdown
        )
        print(f"✅ {out_path}")

    print(f"ℹ️ líneas descartadas: {total_discarded}")


if __name__ == "__main__":
    main()
