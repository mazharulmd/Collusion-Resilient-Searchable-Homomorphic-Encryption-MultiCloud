"""Owner side of a multi-machine deployment: build the encrypted store once and
write two directories.

  OUT/provider/   copy to EVERY provider machine (context, public and evaluation
                  keys, encrypted fast-path columns and cube table; no secret key)
  OUT/client/     stays with the data user (secret key and ground truth)

Fast path: N tags (default 11,580, the primary corpus's tag domain) with
templates count and sum, session-checked layout. Range: a cube with the
primary corpus's dimensions (synthetic records by default, or the real
telemetry / Beijing cube), session-checked layout.

    python scripts/deploy/owner_setup.py --out deploy_bundle
"""
import argparse
import json
import os
import sys

import numpy as np
import openfhe as fhe

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "bench")]
from common import tag_domain_deployment  # noqa: E402
from crshe import corpus, he, rangeagg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=2, help="number of providers")
ap.add_argument("--N", type=int, default=11_580, help="fast-path tag domain")
ap.add_argument("--cube", choices=["synthetic", "telemetry", "beijing", "none"], default="synthetic")
ap.add_argument("--cube-dims", type=int, nargs=3, default=[3, 11_523, 10], help="synthetic cube dims")
ap.add_argument("--cube-records", type=int, default=405_184)
args = ap.parse_args()

prov = os.path.join(args.out, "provider")
cli = os.path.join(args.out, "client")
for d in (os.path.join(prov, "fast"), os.path.join(prov, "cube"), cli):
    os.makedirs(d, exist_ok=True)

bfv = he.BFV()
o, tags, postings, values = tag_domain_deployment(args.N, n=args.n, bfv=bfv, templates=("count", "sum"))
fast = o.fast_layout(["count", "sum"], mac="session")
fast_cts = o.fast_columns(fast)
meta = {"n": args.n, "N": args.N, "slots": bfv.slots, "half": bfv.half,
        "fast": {"templates": fast.templates, "seg": fast.seg, "chunks": fast.chunks, "mac": fast.mac,
                 "files": len(fast_cts)}}
for i, ct in enumerate(fast_cts):
    fhe.SerializeToFile(os.path.join(prov, "fast", f"{i:05d}.bin"), ct, fhe.BINARY)
truth = {"A_count": o.A["count"], "A_sum": o.A["sum"]}

if args.cube != "none":
    if args.cube == "synthetic":
        rng = np.random.default_rng(7)
        dims = tuple(args.cube_dims)
        cells = np.stack([rng.integers(0, dims[0], args.cube_records), np.sort(rng.integers(0, dims[1], args.cube_records)),
                          rng.integers(0, dims[2], args.cube_records)], axis=1)
        cv = rng.integers(1900, 3100, args.cube_records)
    else:
        cb = corpus.cube_telemetry() if args.cube == "telemetry" else corpus.cube_beijing()
        dims, cells, cv = cb.dims, cb.cells, cb.values
    lay, cube_cts = rangeagg.CubeOwner(o).register("cube", dims, cells,
                                                  {"count": np.ones(len(cv), dtype=np.int64), "sum": cv},
                                                  mode="session")
    for i, ct in enumerate(cube_cts):
        fhe.SerializeToFile(os.path.join(prov, "cube", f"{i:05d}.bin"), ct, fhe.BINARY)
    meta["cube"] = {"name": lay.name, "dims": list(lay.dims), "templates": lay.templates, "mode": lay.mode,
                    "seg": lay.seg, "chunks": lay.chunks, "files": len(cube_cts), "source": args.cube}
    truth.update({"cube_cells": cells, "cube_values": cv})

fhe.SerializeToFile(os.path.join(prov, "cc.bin"), bfv.cc, fhe.BINARY)
fhe.SerializeToFile(os.path.join(prov, "pk.bin"), bfv.pk, fhe.BINARY)
bfv.cc.SerializeEvalMultKey(os.path.join(prov, "mult.bin"), fhe.BINARY)
bfv.cc.SerializeEvalAutomorphismKey(os.path.join(prov, "rot.bin"), fhe.BINARY)
json.dump(meta, open(os.path.join(prov, "meta.json"), "w"), indent=1)

fhe.SerializeToFile(os.path.join(cli, "cc.bin"), bfv.cc, fhe.BINARY)
fhe.SerializeToFile(os.path.join(cli, "sk.bin"), bfv.secret_key(), fhe.BINARY)
json.dump(meta, open(os.path.join(cli, "meta.json"), "w"), indent=1)
np.savez_compressed(os.path.join(cli, "truth.npz"), **truth)
size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(prov) for f in fs)
print(f"provider bundle: {prov} ({size / 1e6:.1f} MB), copy it to each of the {args.n} providers")
print(f"client state:    {cli} (keep it with the data user; it holds the secret key)")
