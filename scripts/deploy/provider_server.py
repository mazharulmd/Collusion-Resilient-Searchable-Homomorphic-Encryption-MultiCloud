"""One CR-SHE provider: loads a provider bundle and answers queries over TCP.

    python scripts/deploy/provider_server.py --bundle deploy_bundle/provider --port 9101

Experimental harness: no authentication or TLS. Run it on a private network
or behind a firewall that admits only the client.
"""
import argparse
import glob
import json
import os
import socket
import sys
import time

import numpy as np
import openfhe as fhe

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from crshe import field, he, rangeagg, wire  # noqa: E402
from crshe.protocol import FastLayout, Provider, ProviderBundle  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--bundle", required=True)
ap.add_argument("--host", default="0.0.0.0")
ap.add_argument("--port", type=int, default=9101)
args = ap.parse_args()


class ProviderHE:
    """Evaluation-side handle rebuilt from the serialised context."""

    def __init__(self, cc, pk, slots, half):
        self.cc, self.pk, self.slots, self.half = cc, pk, slots, half

    def encode(self, vec):
        v = np.zeros(self.slots, dtype=np.uint64)
        v[:len(vec)] = vec
        return self.cc.MakePackedPlaintext(field.to_signed(v).tolist())


def load_cts(d, n):
    out = []
    for i in range(n):
        ct, ok = fhe.DeserializeCiphertext(os.path.join(d, f"{i:05d}.bin"), fhe.BINARY)
        if not ok:
            sys.exit(f"cannot read ciphertext {i} in {d}")
        out.append(ct)
    return out


B = args.bundle
meta = json.load(open(os.path.join(B, "meta.json")))
fhe.ReleaseAllContexts()
fhe.ClearEvalMultKeys()
cc, ok1 = fhe.DeserializeCryptoContext(os.path.join(B, "cc.bin"), fhe.BINARY)
pk, ok2 = fhe.DeserializePublicKey(os.path.join(B, "pk.bin"), fhe.BINARY)
ok3 = cc.DeserializeEvalMultKey(os.path.join(B, "mult.bin"), fhe.BINARY)
ok4 = cc.DeserializeEvalAutomorphismKey(os.path.join(B, "rot.bin"), fhe.BINARY)
if not all((ok1, ok2, ok3, ok4)):
    sys.exit("cannot load the bundle's context or keys")
pub = ProviderHE(cc, pk, meta["slots"], meta["half"])
f = meta["fast"]
fl = FastLayout(f["templates"], f["seg"], f["chunks"], f["mac"])
bundle = ProviderBundle(pub, meta["N"], 0)
bundle.fast["stats"] = (fl, load_cts(os.path.join(B, "fast"), f["files"]))
P = Provider(0, bundle)
cube = None
if "cube" in meta:
    c = meta["cube"]
    cube = (rangeagg.CubeLayout(c["name"], tuple(c["dims"]), c["templates"], c["mode"], c["seg"], c["chunks"]),
            load_cts(os.path.join(B, "cube"), c["files"]))
print(f"provider ready on {args.host}:{args.port}  (N={meta['N']}, cube={'yes' if cube else 'no'})", flush=True)

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind((args.host, args.port))
srv.listen(8)
while True:
    conn, peer = srv.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        while True:
            try:
                h, blobs = wire.recv_msg(conn)
            except ConnectionError:
                break
            op = h.get("op")
            t0 = time.perf_counter()
            if op == "ping":
                wire.send_msg(conn, {"ok": True})
                continue
            if op == "quit":
                wire.send_msg(conn, {"ok": True})
                conn.close()
                sys.exit(0)
            keys = wire.keys_from_wire(h["k"], blobs)
            if op == "fast":
                ct = P.fast(keys[0], "stats", compress=True, key_hat=keys[1] if len(keys) > 1 else None)
            elif op == "range" and cube:
                ct = rangeagg.range_answer(pub, cube[0], cube[1], keys, compress=True)
            else:
                wire.send_msg(conn, {"ok": False, "error": f"unknown op {op}"})
                continue
            out = fhe.Serialize(ct, fhe.BINARY)
            wire.send_msg(conn, {"ok": True, "compute_ms": 1e3 * (time.perf_counter() - t0)}, [out])
    finally:
        conn.close()
