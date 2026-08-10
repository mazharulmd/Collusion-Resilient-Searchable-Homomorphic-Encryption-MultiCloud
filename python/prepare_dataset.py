#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Turn a raw IoT corpus into the binary format the C++ side reads.

Two corpora are supported out of the box:

  telemetry  Environmental Sensor Telemetry, 405,184 MQTT messages from three
             Raspberry-Pi sensor arrays (Stafford, 2020).  The primary corpus.
             https://www.kaggle.com/datasets/garystafford/environmental-sensor-data-132k
             file: iot_telemetry_data.csv

  beijing    UCI Beijing Multi-Site Air-Quality, ~420k rows across 12 monitoring
             sites.  The second corpus, added because the primary one has only
             three physical devices, so its tag cardinality comes from time and
             sensor conditions rather than device count.
             https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data
             files: PRSA_Data_*.csv (pass the directory)

Records are indexed under the metadata tags a deployed IoT platform would
attach: device or site identifier, a one-minute time window, and discretised
sensor bands.  The computable field is one sensor reading scaled to an integer.

Usage:
  python3 python/prepare_dataset.py telemetry  path/to/iot_telemetry_data.csv \\
      --out data/telemetry.crshe
  python3 python/prepare_dataset.py beijing    path/to/PRSA_Data_dir \\
      --out data/beijing.crshe

Both writers print the statistics the paper quotes (tag count, posting-list
median/mean/max) and the Lemma 1 magnitude check, so a corpus that would
overflow the plaintext modulus is caught here rather than at decryption.
"""

import argparse
import csv
import glob
import os
import struct
import sys
from collections import defaultdict

MAGIC = b"CRSHEDS1"
DEFAULT_P = 68724326401  # must match crshe::kDefaultModulus


def write_dataset(path, n_records, values, postings_by_tag, tag_names, source):
    """Write the .crshe binary consumed by crshe::Dataset::load."""
    order = sorted(postings_by_tag.keys())
    offset = [0]
    flat = []
    names = []
    for t in order:
        ids = sorted(set(postings_by_tag[t]))
        flat.extend(ids)
        offset.append(len(flat))
        names.append(tag_names.get(t, str(t)))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<QQ", n_records, len(order)))
        f.write(struct.pack("<Q", len(values)))
        f.write(struct.pack("<%dQ" % len(values), *values))
        f.write(struct.pack("<Q", len(offset)))
        f.write(struct.pack("<%dQ" % len(offset), *offset))
        f.write(struct.pack("<Q", len(flat)))
        f.write(struct.pack("<%dI" % len(flat), *flat))
        s = source.encode()
        f.write(struct.pack("<Q", len(s)))
        f.write(s)
        f.write(struct.pack("<Q", len(names)))
        for nm in names:
            b = nm.encode()
            f.write(struct.pack("<I", len(b)))
            f.write(b)
    return order, offset, flat


def report(path, order, offset, flat, values, p):
    lens = [offset[i + 1] - offset[i] for i in range(len(order))]
    lens_sorted = sorted(lens)
    n = len(lens)
    median = lens_sorted[n // 2] if n else 0
    mean = sum(lens) / n if n else 0
    mx = max(lens) if lens else 0

    # Lemma 1: the largest single-tag aggregate must stay below p.
    worst = 0
    for i in range(len(order)):
        s = sum(values[j] for j in flat[offset[i]:offset[i + 1]])
        worst = max(worst, s)

    print(f"\nwrote {path}")
    print(f"  records            : {len(values)}")
    print(f"  tags               : {n}")
    print(f"  postings total     : {len(flat)}")
    print(f"  posting length     : median {median}, mean {mean:.1f}, max {mx}")
    print(f"  value range        : {min(values)} .. {max(values)}")
    print(f"  largest aggregate  : {worst}")
    print(f"  plaintext modulus p: {p}")
    if worst >= p:
        print("  LEMMA 1 VIOLATED: the largest aggregate exceeds p. Aggregates "
              "would wrap. Raise p (prime, = 1 mod 2*ring_dim) or rescale the "
              "computable field with --scale.", file=sys.stderr)
        sys.exit(2)
    print(f"  Lemma 1 headroom   : {p / max(1, worst):.1f}x  OK")
    print(f"  masked index at full scale: "
          f"{n * len(values) * 8 / 1e9:.1f} GB per provider "
          f"(this is why the general path is measured on subsamples)")


def band(value, edges):
    for i, e in enumerate(edges):
        if value <= e:
            return i
    return len(edges)


def quantile_edges(vals, k):
    s = sorted(vals)
    return [s[int(len(s) * (i + 1) / k) - 1] for i in range(k - 1)]


def build_telemetry(src, out, scale, bands, p):
    rows = []
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    if not rows:
        sys.exit("empty CSV")

    numeric = ["co", "humidity", "lpg", "smoke", "temp"]
    cols = {c: [float(r[c]) for r in rows] for c in numeric}
    edges = {c: quantile_edges(cols[c], bands) for c in numeric}

    values = []
    postings = defaultdict(list)
    names = {}
    for i, r in enumerate(rows):
        temp = float(r["temp"])
        values.append(int(round(temp * scale)))

        add = lambda t: (postings[t].append(i), names.setdefault(t, t))
        add("dev:" + r["device"])
        # One-minute time window, as a deployed platform would attach.
        ts = int(float(r["ts"]))
        add("min:%d" % (ts // 60))
        for c in numeric:
            add("%s:b%d" % (c, band(float(r[c]), edges[c])))
        add("light:" + ("1" if str(r["light"]).lower() in ("true", "1") else "0"))
        add("motion:" + ("1" if str(r["motion"]).lower() in ("true", "1") else "0"))

    if min(values) < 0:
        sys.exit("negative computable field; pass --offset to shift it "
                 "non-negative and record the offset in the paper")
    o, off, flat = write_dataset(out, len(values), values, postings, names,
                                 "environmental-sensor-telemetry")
    report(out, o, off, flat, values, p)


def build_beijing(src, out, scale, bands, p):
    files = sorted(glob.glob(os.path.join(src, "PRSA_Data_*.csv"))) \
        if os.path.isdir(src) else [src]
    if not files:
        sys.exit("no PRSA_Data_*.csv found in " + src)

    raw = []
    for path in files:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                raw.append(r)

    # This corpus has missing values (UCI flags it), and they must not be
    # confused with real readings:
    #
    #   * A sensor channel reading "NA" is given its own tag, `<chan>:na`, not
    #     folded into the lowest quantile band. CO alone is NA in 4.9% of rows;
    #     mapping those to band 0 would put "sensor down" and "clean air" under
    #     the same tag, which would corrupt both the posting-length distribution
    #     and the per-class leakage analysis that depends on tag semantics.
    #   * A row whose TEMP is missing is dropped entirely (398 rows, 0.09%),
    #     because TEMP is the computable field and an aggregate must never sum
    #     an invented value.
    numeric = ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3", "PRES", "DEWP"]

    def val(r, k):
        """Reading as a float, or None when absent."""
        v = r.get(k, "")
        if v in ("NA", "", None):
            return None
        try:
            return float(v)
        except ValueError:
            return None

    rows = [r for r in raw if val(r, "TEMP") is not None]
    dropped = len(raw) - len(rows)

    # Quantile edges from observed readings only, so the bands describe the
    # data rather than the missingness.
    edges = {}
    for c in numeric:
        obs = [v for v in (val(r, c) for r in rows) if v is not None]
        edges[c] = quantile_edges(obs, bands) if obs else []

    values = []
    postings = defaultdict(list)
    names = {}
    na_counts = defaultdict(int)
    for i, r in enumerate(rows):
        t = val(r, "TEMP")
        values.append(int(round((t + 50.0) * scale)))   # TEMP can be negative

        def add(tag):
            postings[tag].append(i)
            names.setdefault(tag, tag)

        add("site:" + r.get("station", "?"))
        add("hour:%s-%s-%s-%s" % (r.get("year"), r.get("month"), r.get("day"),
                                  r.get("hour")))
        wd = r.get("wd", "NA")
        add("wd:" + (wd if wd not in ("NA", "", None) else "na"))
        for c in numeric:
            v = val(r, c)
            if v is None:
                add("%s:na" % c)
                na_counts[c] += 1
            else:
                add("%s:b%d" % (c, band(v, edges[c])))

    if min(values) < 0:
        sys.exit("negative computable field after the +50C shift; widen it")

    print(f"  dropped {dropped} row(s) with a missing TEMP "
          f"({100.0 * dropped / max(1, len(raw)):.2f}%)")
    if na_counts:
        print("  missing readings given an explicit ':na' tag rather than "
              "band 0:")
        for c, k in sorted(na_counts.items(), key=lambda kv: -kv[1]):
            print(f"    {c:<7} {k:>6} ({100.0 * k / len(rows):.2f}%)")

    o, off, flat = write_dataset(out, len(values), values, postings, names,
                                 "uci-beijing-multi-site-air-quality"
                                 " (TEMP shifted by +50C before scaling; rows "
                                 "with missing TEMP dropped; missing sensor "
                                 "readings tagged ':na')")
    report(out, o, off, flat, values, p)


def build_synthetic(out, n_tags, n_records, p):
    """Deterministic stand-in so the whole harness runs before any download."""
    import random
    rng = random.Random(99)
    values = [1000 + rng.randrange(2500) for _ in range(n_records)]
    postings = defaultdict(list)
    names = {}
    for x in range(n_tags):
        ln = max(1, min(n_records, int(n_records / ((x + 1) ** 1.15))))
        ids = rng.sample(range(n_records), ln)
        t = "syn%d" % x
        postings[t] = ids
        names[t] = t
    o, off, flat = write_dataset(out, n_records, values, postings, names,
                                 "synthetic")
    report(out, o, off, flat, values, p)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", choices=["telemetry", "beijing", "synthetic"])
    ap.add_argument("source", nargs="?", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=100,
                    help="integer scale for the computable field (default 100)")
    ap.add_argument("--bands", type=int, default=10,
                    help="quantile bands per sensor (default 10)")
    ap.add_argument("--p", type=int, default=DEFAULT_P)
    ap.add_argument("--ntags", type=int, default=15347)
    ap.add_argument("--nrecords", type=int, default=405184)
    a = ap.parse_args()

    if a.corpus == "synthetic":
        build_synthetic(a.out, a.ntags, a.nrecords, a.p)
    elif not a.source:
        sys.exit("a source path is required for " + a.corpus)
    elif a.corpus == "telemetry":
        build_telemetry(a.source, a.out, a.scale, a.bands, a.p)
    else:
        build_beijing(a.source, a.out, a.scale, a.bands, a.p)


if __name__ == "__main__":
    main()
