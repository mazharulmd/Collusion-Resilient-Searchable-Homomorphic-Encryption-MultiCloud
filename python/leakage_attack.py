#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E6: a frequency/volume leakage-abuse attack against our own index.

The attack is run twice against the same corpus:

  (a) against an unmasked replicated index, whose rows expose their Hamming
      weight, i.e. the posting-list length of every tag;
  (b) against the masked index of Section V-C, whose rows are I'[x][i] =
      I[x][i] + F'_{K'}(x||i) mod p.

The adversary's auxiliary knowledge is the tag-frequency distribution of a
similar deployment, modelled as the true distribution observed on a held-out
sample of the records (--aux-fraction) rather than as exact knowledge, so the
attack is not handed the answer.

Attack: match each observed row statistic to the auxiliary frequency it is
closest to, and count a tag as re-identified when the match is correct.  On
the unmasked index the statistic is the row weight and the matching is close to
an isomorphism wherever posting lengths are distinct.  On the masked index the
statistic is a sum of pseudorandom values, so the same procedure recovers
nothing beyond chance -- which is the empirical counterpart of Theorem 1.

Input is the CSV produced by build/dump_index_stats, which computes the masked
row sums with the real PRF.

  build/dump_index_stats --data=data/telemetry.crshe \\
      --out=bench/results/telemetry/e6_index_stats.csv
  python3 python/leakage_attack.py \\
      --stats bench/results/telemetry/e6_index_stats.csv \\
      --out bench/results/telemetry/e6_leakage.csv
"""

import argparse
import csv
import math
import random
import sys
from collections import Counter, defaultdict


def load(path):
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "idx": int(r["tag_index"]),
                "name": r["tag_name"],
                "weight": int(r["unmasked_weight"]),
                "masked": int(r["masked_rowsum"]),
                "p": int(r["p"]),
                "N": int(r["N"]),
                "Nd": int(r["Nd"]),
            })
    if not rows:
        sys.exit("no rows in " + path)
    return rows


def auxiliary_frequencies(rows, fraction, seed):
    """What the adversary knows: tag frequencies from a similar deployment.

    Modelled by binomially thinning each true posting length, which is what
    observing a `fraction` sample of the records would give.
    """
    rng = random.Random(seed)
    aux = {}
    for r in rows:
        w = r["weight"]
        # Normal approximation to Binomial(w, fraction), rescaled back.
        mean = w * fraction
        sd = math.sqrt(max(0.0, w * fraction * (1 - fraction)))
        obs = max(0.0, rng.gauss(mean, sd))
        aux[r["idx"]] = obs / fraction if fraction > 0 else 0.0
    return aux


def match_attack(observed, aux, window=32):
    """Greedy nearest-frequency matching.

    `observed` maps tag index -> statistic the adversary sees at rest.
    `aux` maps tag index -> frequency the adversary expects from a similar
    deployment.  Returns the number of tags assigned to their own identity.
    """
    import bisect
    aux_items = sorted(aux.items(), key=lambda kv: kv[1])
    aux_vals = [v for _, v in aux_items]
    aux_ids = [k for k, _ in aux_items]

    obs_items = sorted(observed.items(), key=lambda kv: kv[1])
    used = set()
    correct = 0
    for tag, val in obs_items:
        lo = bisect.bisect_left(aux_vals, val)
        best, bestd = None, None
        for j in range(max(0, lo - window), min(len(aux_vals), lo + window)):
            if aux_ids[j] in used:
                continue
            d = abs(aux_vals[j] - val)
            if bestd is None or d < bestd:
                best, bestd = aux_ids[j], d
        if best is None:
            continue
        used.add(best)
        if best == tag:
            correct += 1
    return correct


def match_attack_scored(observed, aux, score_ids, window=32):
    """As match_attack, but counts only assignments whose true tag is in
    `score_ids`.  The matching itself still runs over the whole universe, so
    restricting the score does not give the adversary extra information."""
    import bisect
    aux_items = sorted(aux.items(), key=lambda kv: kv[1])
    aux_vals = [v for _, v in aux_items]
    aux_ids = [k for k, _ in aux_items]
    obs_items = sorted(observed.items(), key=lambda kv: kv[1])
    used = set()
    correct = 0
    for tag, val in obs_items:
        lo = bisect.bisect_left(aux_vals, val)
        best, bestd = None, None
        for j in range(max(0, lo - window), min(len(aux_vals), lo + window)):
            if aux_ids[j] in used:
                continue
            d = abs(aux_vals[j] - val)
            if bestd is None or d < bestd:
                best, bestd = aux_ids[j], d
        if best is None:
            continue
        used.add(best)
        if best == tag and tag in score_ids:
            correct += 1
    return correct


def unique_volume_pct(observed):
    """Ceiling of a pure volume attack: the fraction of tags whose observed
    statistic is unique in the corpus.

    With perfect auxiliary knowledge every such tag is re-identified with
    certainty, so this is the strongest claim volume leakage alone supports and
    it does not depend on how good the matcher is.  It is the number to quote
    as the leakage of an unmasked replicated index.
    """
    counts = Counter(observed.values())
    return 100.0 * sum(1 for v in observed.values() if counts[v] == 1) / len(observed)


def tag_class(name):
    """Metadata class a tag belongs to, from the prefix the indexer assigns.

    The corpus's tag universe is dominated by one-minute time buckets, which
    all have near-identical posting lengths and are therefore intrinsically
    hard to tell apart by volume alone.  Aggregating over the whole universe
    hides that the *distinctive* metadata -- device identity, sensor bands,
    light and motion flags -- is recovered almost perfectly.  Reporting per
    class is both more informative and more honest than a single number, and
    it is what the leakage-abuse literature does.
    """
    return name.split(":", 1)[0] if ":" in name else "other"


def uniformity(values, p, bins=64):
    """Chi-square statistic of `values` against Uniform(Z_p).

    Reported for the masked rows: a coalition observing them should not be able
    to distinguish them from uniform, which is what Theorem 1 claims.
    """
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    counts = Counter(min(bins - 1, v * bins // p) for v in values)
    expect = n / bins
    chi2 = sum((counts.get(b, 0) - expect) ** 2 / expect for b in range(bins))
    # Wilson-Hilferty normal approximation to the chi-square tail.
    k = bins - 1
    z = ((chi2 / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    pval = 0.5 * math.erfc(z / math.sqrt(2))
    return chi2, pval


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", required=True,
                    help="CSV from build/dump_index_stats")
    ap.add_argument("--out", default="bench/results/e6_leakage.csv")
    ap.add_argument("--aux-fractions", default="1.0,0.9,0.75,0.5,0.25",
                    help="fractions of the records the adversary has seen")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    rows = load(a.stats)
    p = rows[0]["p"]
    N, Nd = rows[0]["N"], rows[0]["Nd"]
    fractions = [float(x) for x in a.aux_fractions.split(",") if x]

    unmasked = {r["idx"]: float(r["weight"]) for r in rows}
    masked = {r["idx"]: float(r["masked"]) for r in rows}
    chance = 100.0 / len(rows)

    uniq_unmasked = unique_volume_pct(unmasked)
    uniq_masked = unique_volume_pct(masked)
    chi2, pval = uniformity([r["masked"] for r in rows], p)

    med = lambda v: sorted(v)[len(v) // 2]

    # Per-class breakdown at perfect auxiliary knowledge, which is the ceiling.
    by_class = defaultdict(list)
    for r in rows:
        by_class[tag_class(r["name"])].append(r["idx"])
    aux_perfect = auxiliary_frequencies(rows, 1.0, a.seed)
    class_rows = []
    for cls, ids in sorted(by_class.items()):
        sub_un = {i: unmasked[i] for i in ids}
        sub_ma = {i: masked[i] for i in ids}
        # Match within the whole universe, then score only this class, so the
        # adversary is not handed the partition as extra knowledge.
        n_un = match_attack_scored(unmasked, aux_perfect, set(ids))
        n_ma = match_attack_scored(masked, aux_perfect, set(ids))
        class_rows.append((cls, len(ids), 100.0 * n_un / len(ids),
                           100.0 * n_ma / len(ids)))
        del sub_un, sub_ma

    out_rows = []
    for frac in fractions:
        ra, rb = [], []
        for t in range(a.trials):
            aux = auxiliary_frequencies(rows, frac, a.seed + t)
            ra.append(100.0 * match_attack(unmasked, aux) / len(rows))
            rb.append(100.0 * match_attack(masked, aux) / len(rows))
        out_rows.append(("unmasked", frac, med(ra), min(ra), max(ra)))
        out_rows.append(("masked (CR-SHE)", frac, med(rb), min(rb), max(rb)))

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index_variant", "N", "Nd", "trials", "aux_fraction",
                    "reidentification_pct_median", "reidentification_pct_min",
                    "reidentification_pct_max", "chance_pct",
                    "unique_volume_ceiling_pct", "chi2_vs_uniform", "chi2_p_value",
                    "note"])
        for variant, frac, m, lo, hi in out_rows:
            masked_row = variant.startswith("masked")
            w.writerow([variant, N, Nd, a.trials, frac, m, lo, hi, chance,
                        uniq_masked if masked_row else uniq_unmasked,
                        f"{chi2:.2f}" if masked_row else "",
                        f"{pval:.4f}" if masked_row else "",
                        "row statistic is a sum of PRF outputs; "
                        "indistinguishable from uniform over Z_p (Theorem 1)"
                        if masked_row else
                        "row Hamming weight = posting-list length, directly "
                        "observable at rest"])

    print(f"corpus: N={N} tags, N_d={Nd} records, p={p}")
    print(f"{a.trials} trials per point\n")
    print("  unique-volume ceiling (perfect auxiliary knowledge):")
    print(f"    unmasked index : {uniq_unmasked:6.2f}% of tags have a unique "
          f"posting-list length")
    print(f"    masked index   : {uniq_masked:6.2f}% -- but the statistic is a "
          f"pseudorandom sum,")
    print( "                     so uniqueness carries no information about the tag")
    print()
    print("  matching attack, by adversary auxiliary knowledge:")
    print("    aux sample   unmasked      masked      chance")
    for frac in fractions:
        ua = [r for r in out_rows if r[0] == "unmasked" and r[1] == frac][0]
        mb = [r for r in out_rows if r[0].startswith("masked") and r[1] == frac][0]
        print(f"      {frac:5.0%}    {ua[2]:8.2f}%   {mb[2]:8.2f}%   {chance:8.4f}%")
    print()
    print(f"  masked row sums vs Uniform(Z_p): chi2={chi2:.2f} on 63 df, p={pval:.4f}")
    print( "  (a large p-value means the masked rows are not distinguishable from")
    print( "   uniform, which is what Theorem 1 asserts; it is not itself a proof.)")
    cls_out = a.out.replace(".csv", "_by_class.csv")
    with open(cls_out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag_class", "tags_in_class",
                    "unmasked_reidentification_pct", "masked_reidentification_pct",
                    "aux_fraction", "note"])
        for cls, n, u, m in class_rows:
            w.writerow([cls, n, f"{u:.2f}", f"{m:.2f}", 1.0,
                        "perfect auxiliary knowledge; matching runs over the "
                        "whole tag universe, scored on this class only"])

    print()
    print("  per tag class, at perfect auxiliary knowledge:")
    print("    class        tags    unmasked    masked")
    for cls, n, u, m in sorted(class_rows, key=lambda t: -t[2]):
        print(f"    {cls:<11} {n:>6}   {u:8.2f}%  {m:7.2f}%")
    print(f"\nwrote {a.out}")
    print(f"wrote {cls_out}")


if __name__ == "__main__":
    main()
