"""Oblivious range aggregation over registered data cubes.

The owner registers a data cube: d ordered tag families (for example device,
one-minute window and a sensor's value band), each record falling in exactly
one cell. For every registered template it stores the d-dimensional prefix
sums (the summed-area table, SAT) of the per-cell aggregates, flattened row-major
and encrypted like a fast-path column.

The aggregate over any box [lo_1, hi_1] x ... x [lo_d, hi_d] is, by
inclusion-exclusion, a signed sum of 2^d SAT entries at the box's corners. The
user sends one DPF key per corner, with output beta = +1 or -1 (p - 1) by the
corner's parity. A corner that falls outside the cube (lo_k = 0) contributes
nothing, but its key is still sent, as a beta = 0 key at a random point, so
every query to a cube carries exactly 2^d keys and a provider cannot tell a
range that touches the cube's edge. Each provider contracts the corner
shares against the encrypted SAT and returns one ciphertext.

Two layouts:
  per_corner  corner r's contraction lands in its own slot segment, so the
              user receives each signed corner value and checks it against a
              per-cell MAC key; consistent substitutions are caught as on the
              fast path. Costs 2^d segments per template.
  combined    the provider adds the corner shares first and contracts once;
              the user checks one global MAC, which (as on the flexible path)
              does not catch a consistent linear substitution.
  session     the combined layout with row 1 holding a COPY of the table. The
              user sends a second set of 2^d keys whose outputs are the corner
              signs times a fresh secret delta_s, and checks yhat == delta_s*y.
              Any response that changes the answer is accepted with
              probability at most 1/p plus the DPF advantage. Combined cost
              and storage, twice the keys and DPF evaluation.

Cost per provider: 2^d full-domain DPF evaluations over the M = prod(dims)
cells and ceil(k M / (ell/2)) plaintext-ciphertext products, with k segments,
independent of the record count and of the box.
"""
import os
from dataclasses import dataclass

import numpy as np

from . import dpf, field, he, prg

DOMAIN_CUBE_MAC = 4


@dataclass
class CubeLayout:
    name: str
    dims: tuple
    templates: list
    mode: str               # "per_corner", "combined" or "session"
    seg: int
    chunks: int
    role: object = None

    @property
    def d(self):
        return len(self.dims)

    @property
    def M(self):
        return int(np.prod(self.dims))

    @property
    def corners(self):
        return 1 << self.d

    def segment(self, r, t):
        return (r * len(self.templates) + t) if self.mode == "per_corner" else t


def summed_area(cells, dims, coeff):
    """d-dimensional prefix sums of per-cell sums of `coeff`, flattened."""
    flat = np.ravel_multi_index(tuple(np.asarray(cells).T), dims)
    cube = np.zeros(int(np.prod(dims)), dtype=np.int64)
    np.add.at(cube, flat, np.asarray(coeff, dtype=np.int64))
    sat = cube.reshape(dims)
    for axis in range(len(dims)):
        sat = np.cumsum(sat, axis=axis)
    return sat.reshape(-1)


def corners(box, dims):
    """[(mask, flat index or None, beta)] for the 2^d corners of the box.
    The corner for mask takes lo_k - 1 on the axes whose bit is set, hi_k
    elsewhere, with sign (-1)^popcount(mask). None marks a corner outside
    the cube, which contributes zero."""
    d = len(dims)
    out = []
    for mask in range(1 << d):
        coord = []
        for k, (lo, hi) in enumerate(box):
            if not 0 <= lo <= hi < dims[k]:
                raise ValueError(f"bad range on axis {k}: [{lo}, {hi}] in [0, {dims[k]})")
            coord.append(lo - 1 if mask >> k & 1 else hi)
        sign = -1 if bin(mask).count("1") % 2 else 1
        if min(coord) < 0:
            out.append((mask, None, 0))
        else:
            out.append((mask, int(np.ravel_multi_index(coord, dims)), sign % field.P))
    return out


class CubeOwner:
    """Registers cubes on behalf of a protocol.Owner (same keys and BFV)."""

    def __init__(self, owner):
        self.owner = owner
        self.bfv = owner.bfv
        self.mac_keys = {}
        self.sat = {}

    def register(self, name, dims, cells, templates, mode="per_corner", cube_id=1, role=None):
        """With a role, only that role's records enter the table, so any box
        a role-r user asks for aggregates role-r records only."""
        if mode not in ("per_corner", "combined", "session"):
            raise ValueError(f"unknown layout {mode}")
        templates = {t: self.owner.role_coeff(c, role) for t, c in templates.items()}
        dims = tuple(int(x) for x in dims)
        names = list(templates)
        k = len(names) * ((1 << len(dims)) if mode == "per_corner" else 1)
        kpow = 1 << max(0, (k - 1).bit_length())
        seg = self.bfv.half // kpow
        if seg < 1:
            raise ValueError("too many segments for one ciphertext")
        M = int(np.prod(dims))
        layout = CubeLayout(name, dims, names, mode, seg, -(-M // seg), role)
        sats = {}
        for t in names:
            s = summed_area(cells, dims, templates[t])
            field.check_magnitude([int(s.max(initial=0))])     # whole-cube total < p
            sats[t] = s.astype(np.uint64)
        if mode == "per_corner":
            keys = prg.uniform_zp(self.owner.K_rowmac, DOMAIN_CUBE_MAC, cube_id, M)
            keys[keys == 0] = 1
        else:
            keys = None
        self.mac_keys[name] = keys
        self.sat[name] = sats
        return layout, self._encrypt(layout, sats, keys)

    def _encrypt(self, layout, sats, keys):
        H, seg = self.bfv.half, layout.seg
        reps = layout.corners if layout.mode == "per_corner" else 1
        if layout.mode == "session":
            macs = sats             # row 1 is a copy; the key rides in the query
        else:
            macs = {t: field.mul(s, keys) if keys is not None else field.mul(s, np.uint64(self.owner.delta))
                    for t, s in sats.items()}
        cts = []
        for c in range(layout.chunks):
            lo, hi = c * seg, min((c + 1) * seg, layout.M)
            v = np.zeros(self.bfv.slots, dtype=np.uint64)
            for r in range(reps):
                for ti, t in enumerate(layout.templates):
                    g = layout.segment(r, ti) * seg
                    v[g:g + hi - lo] = sats[t][lo:hi]
                    v[H + g:H + g + hi - lo] = macs[t][lo:hi]
            cts.append(self.bfv.encrypt(v))
        return cts

    def client_secret(self, name):
        return self.mac_keys[name]


def range_token(layout, box, n):
    """User side: 2^d corner keys per provider, plus the user's record of
    which corners are real. Every query to a cube sends the same number of
    keys, real or dummy. In the session layout each provider's list holds
    2^d keys for the signs followed by 2^d keys for delta_s times the signs,
    and meta ends with ("session", delta_s)."""
    from .protocol import fresh_unit
    keys = [[] for _ in range(n)]
    meta = []
    for mask, x, beta in corners(box, layout.dims):
        alpha = x if x is not None else int.from_bytes(os.urandom(8), "big") % layout.M
        for j, k in enumerate(dpf.gen(alpha, layout.M, n, beta=beta)):
            keys[j].append(k)
        meta.append((mask, x, beta, alpha))
    if layout.mode == "session":
        ds = fresh_unit()
        for mask, x, beta, alpha in meta:
            for j, k in enumerate(dpf.gen(alpha, layout.M, n, beta=beta * ds % field.P)):
                keys[j].append(k)
        meta.append(("session", ds))
    return keys, meta


def range_answer(public_he, layout, cts, corner_keys, compress=False):
    """Provider side: evaluate every corner key over the whole cube and
    contract against the encrypted SAT. Returns one ciphertext."""
    want = layout.corners * (2 if layout.mode == "session" else 1)
    if len(corner_keys) != want:
        raise ValueError("a query must carry one key per corner")
    for k in corner_keys:
        if k.N != layout.M:
            raise ValueError("key domain does not match the cube")
    cc, H, seg = public_he.cc, public_he.half, layout.seg

    def total(ks):
        e = ks[0].eval_full()
        for k in ks[1:]:
            e = field.add(e, k.eval_full())
        return e

    if layout.mode == "per_corner":
        evals = [(k.eval_full(),) * 2 for k in corner_keys]
    elif layout.mode == "combined":
        e = total(corner_keys)
        evals = [(e, e)]
    else:                                   # session: row 0 signs, row 1 delta_s * signs
        evals = [(total(corner_keys[:layout.corners]), total(corner_keys[layout.corners:]))]
    acc = None
    for c, ct in enumerate(cts):
        lo, hi = c * seg, min((c + 1) * seg, layout.M)
        v = np.zeros(public_he.slots, dtype=np.uint64)
        for r, (e, eh) in enumerate(evals):
            for ti in range(len(layout.templates)):
                g = layout.segment(r, ti) * seg
                v[g:g + hi - lo] = e[lo:hi]
                v[H + g:H + g + hi - lo] = eh[lo:hi]
        acc = he.add(cc, acc, cc.EvalMult(ct, public_he.encode(v)))
    acc = he.segment_sum(cc, acc, seg)
    return he.compress(cc, acc) if compress else acc


def finish_range(user, layout, mac_keys, meta, responses):
    """User side: combine, check every MAC, and add the signed corners."""
    from .protocol import VerificationError
    slots = user._combine(responses)
    H, seg = user.bfv.half, layout.seg
    out = {}
    for ti, t in enumerate(layout.templates):
        if layout.mode in ("combined", "session"):
            g = layout.segment(0, ti) * seg
            y, yh = int(slots[g]), int(slots[H + g])
            key = meta[-1][1] if layout.mode == "session" else user.delta
            if yh != y * key % field.P:
                raise VerificationError(f"MAC check failed for {t}")
            out[t] = y
            continue
        total = 0
        for r, (mask, x, beta, alpha) in enumerate(meta):
            g = layout.segment(r, ti) * seg
            y, yh = int(slots[g]), int(slots[H + g])
            if x is None:                       # dummy corner: must be exactly zero
                if y or yh:
                    raise VerificationError(f"dummy corner {mask} of {t} is non-zero")
                continue
            if yh != y * int(mac_keys[x]) % field.P:
                raise VerificationError(f"MAC check failed for corner {mask} of {t}")
            total = (total + y) % field.P
        out[t] = total
    return out
