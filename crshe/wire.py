"""Wire format for the multi-machine deployment (scripts/deploy/).

A message is a 4-byte big-endian header length, a JSON header, then raw binary
blobs whose lengths the header lists. DPF keys travel as their fields; nothing
is pickled, so a provider never unpickles network input.
"""
import json
import socket
import struct

import numpy as np

from . import dpf


def send_msg(sock, header, blobs=()):
    blobs = [bytes(b) for b in blobs]
    head = json.dumps({**header, "_blobs": [len(b) for b in blobs]}).encode()
    sock.sendall(struct.pack(">I", len(head)) + head + b"".join(blobs))


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(1 << 20, n - len(buf)))
        if not chunk:
            raise ConnectionError("peer closed the connection")
        buf += chunk
    return bytes(buf)


def recv_msg(sock):
    (n,) = struct.unpack(">I", _recv_exact(sock, 4))
    if n > 1 << 24:
        raise ValueError("header too large")
    header = json.loads(_recv_exact(sock, n))
    blobs = [_recv_exact(sock, k) for k in header.pop("_blobs")]
    return header, blobs


def key_to_wire(k):
    """(json-able dict, blobs) for a DPF key."""
    if isinstance(k, dpf.TreeKey):
        return ({"t": "tree", "party": k.party, "cw_out": int(k.cw_out), "depth": k.depth, "N": k.N},
                [k.seed.tobytes(), k.cw_seed.tobytes(), k.cw_tl.tobytes(), k.cw_tr.tobytes()])
    if isinstance(k, dpf.SeedKey):
        return {"t": "seed", "party": k.party, "N": k.N}, [bytes(k.seed)]
    if isinstance(k, dpf.VectorKey):
        return {"t": "vec", "party": k.party, "N": k.N}, [np.asarray(k.vec, dtype="<u8").tobytes()]
    raise TypeError(type(k))


def key_from_wire(d, blobs):
    if d["t"] == "tree":
        seed, cws, tl, tr = blobs
        return dpf.TreeKey(d["party"], np.frombuffer(seed, np.uint8).reshape(1, -1).copy(),
                           np.frombuffer(cws, np.uint8).reshape(d["depth"], -1).copy(),
                           np.frombuffer(tl, np.uint8).copy(), np.frombuffer(tr, np.uint8).copy(),
                           int(d["cw_out"]), int(d["depth"]), int(d["N"]))
    if d["t"] == "seed":
        return dpf.SeedKey(d["party"], blobs[0], int(d["N"]))
    if d["t"] == "vec":
        return dpf.VectorKey(d["party"], np.frombuffer(blobs[0], "<u8").astype(np.uint64), int(d["N"]))
    raise ValueError(d["t"])


def keys_to_wire(keys):
    """A list of keys -> (list of dicts, flat blobs, blob counts)."""
    ds, blobs, counts = [], [], []
    for k in keys:
        d, b = key_to_wire(k)
        ds.append(d)
        blobs += b
        counts.append(len(b))
    return {"keys": ds, "counts": counts}, blobs


def keys_from_wire(meta, blobs):
    out, i = [], 0
    for d, c in zip(meta["keys"], meta["counts"]):
        out.append(key_from_wire(d, blobs[i:i + c]))
        i += c
    return out


def connect(addr, timeout=600):
    host, port = addr.rsplit(":", 1)
    s = socket.create_connection((host, int(port)), timeout=timeout)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return s
