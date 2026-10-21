"""Frequency attack (Section 10.9 of the revised manuscript) against four index representations:
unmasked, padded to the next power of two, volume-hiding (all rows padded to
the maximum), and the CR-SHE masked index. Per tag class, for several levels
of auxiliary knowledge. Requires the real corpora (data/README.md).
"""
import argparse
import sys

from common import save
from crshe import attack, corpus

ap = argparse.ArgumentParser()
ap.add_argument("--corpus", choices=["telemetry", "beijing"], default="telemetry")
ap.add_argument("--fractions", type=float, nargs="+", default=[1.0, 0.5, 0.1, 0.01])
args = ap.parse_args()

loader = corpus.load_telemetry if args.corpus == "telemetry" else corpus.load_beijing
try:
    c = loader()
except (FileNotFoundError, OSError) as exc:
    sys.exit(f"corpus not available: {exc}  (see data/README.md)")

L = c.lengths()
key = bytes(range(16))          # fixed public seed: the experiment reproduces bit for bit
runs = []
for frac in args.fractions:
    for scheme in ("unmasked", "padded", "volume_hiding", "masked"):
        r = attack.run(L, c.tag_class, scheme, fraction=frac, key=key, n_records=c.Nd)
        runs.append(r)
        print(f"f={frac:<5} {scheme:14s} overall={100*r['overall']:7.3f}%  " +
              " ".join(f"{k}={100*v:.1f}%" for k, v in r["per_class"].items()))
save(f"leakage_{args.corpus}.json", {"corpus": c.summary(), "runs": runs})
