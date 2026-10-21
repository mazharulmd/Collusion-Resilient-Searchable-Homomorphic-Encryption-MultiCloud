"""CR-SHE parties: data owner, cloud provider, data user.

Query paths
-----------
fast       registered single-keyword templates. Each provider folds its DPF
           share e_j into the precomputed encrypted columns A_f and returns
           ONE ciphertext: row 0 carries the value share, row 1 the MAC share,
           and up to H/seg templates sit side by side in segments.
legacy     the submitted manuscript's layout, kept as a baseline: value and
           MAC as two separate ciphertexts, each summed over all 8,192 slots.
retrieve   providers return b_j = sum_x e_j[x] I'[x] over the masked index;
           the user subtracts the mask row and obtains the posting list.
flexible   two rounds. Retrieve, then the user forms any selection vector it
           likes from the posting lists (conjunctions, ad-hoc weights), deals
           it as fresh additive shares, and each provider contracts its share
           against the encrypted record column. Every share a coalition of
           n-1 providers sees is uniform, so the round leaks nothing; this
           replaces the submitted general path, whose mask-correction column
           had to be precomputed per weight vector and so could not serve
           ad-hoc weights at all.
"""
import os
from dataclasses import dataclass, field as dc_field

import numpy as np

from . import dpf, field, he, prg


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def matvec_mod(e, M, block=64):
    """sum_x e[x] * M[x] mod p for e in Z_p^N and M in Z_p^{N x N_d}.

    e is split into a 19-bit and an 18-bit limb, so each product is below
    2^56 and a block of 64 rows sums below 2^62 before it is reduced.
    """
    e = np.asarray(e, dtype=np.uint64)
    e0 = e & np.uint64((1 << 19) - 1)
    e1 = e >> np.uint64(19)
    acc0 = np.zeros(M.shape[1], dtype=np.uint64)
    acc1 = np.zeros(M.shape[1], dtype=np.uint64)
    for s in range(0, M.shape[0], block):
        acc0 = field.add(acc0, (e0[s:s + block] @ M[s:s + block]) % np.uint64(field.P))
        acc1 = field.add(acc1, (e1[s:s + block] @ M[s:s + block]) % np.uint64(field.P))
    return field.add(acc0, field.mul(acc1, np.uint64((1 << 19) % field.P)))


def mask_rows(key, rows, n_records):
    """One-time-pad mask P[x] for each x in `rows`, exactly uniform on Z_p."""
    return np.stack([prg.uniform_zp(key, prg.DOMAIN_MASK, x, n_records) for x in rows])


def row_mac_keys(key, N):
    d = prg.uniform_zp(key, prg.DOMAIN_ROWMAC, 0, N)
    d[d == 0] = 1           # probability N/p; keeps every key a unit
    return d


@dataclass
class FastLayout:
    """Which templates share one response, and how the slots are cut."""
    templates: list
    seg: int
    chunks: int
    mac: str                # "row" (per-row keys) or "global"


# ---------------------------------------------------------------------------
# data owner
# ---------------------------------------------------------------------------
class Owner:
    """Holds the plaintext records, the dictionary and every secret."""

    def __init__(self, tags, postings, values, templates, n, N=None, bfv=None,
                 seed=None, build_masked_index=False):
        """
        tags       list of tag names; row of tag k is k (sorted order is the
                   caller's choice, rows never move)
        postings   list of int arrays, record ids carrying each tag
        values     computable field m_i, non-negative ints
        templates  dict name -> coefficient vector c_f[i] = w_f[i] * m_i
        n          number of providers
        N          tag domain (>= len(tags)); free rows are all-zero rows
        seed       fixes the owner's keys for reproducible experiments only
        """
        self.tags = list(tags)
        self.D = {t: i for i, t in enumerate(self.tags)}
        self.postings = [np.asarray(p, dtype=np.int64) for p in postings]
        self.values = np.asarray(values, dtype=np.int64)
        self.Nd = len(self.values)
        self.N = N or len(self.tags)
        if self.N < len(self.tags):
            raise ValueError("tag domain smaller than vocabulary")
        self.n = n
        rnd = np.random.default_rng(seed) if seed is not None else None
        draw = (lambda k: rnd.bytes(k)) if rnd is not None else os.urandom
        self.K_mask = draw(16)
        self.K_rowmac = draw(16)
        self.delta = 1 + int.from_bytes(draw(8), "big") % (field.P - 1)
        self.bfv = bfv or he.BFV()
        self.templates = {}
        self.A = {}
        for name, coeff in templates.items():
            coeff = np.asarray(coeff, dtype=np.int64)
            if (coeff < 0).any():
                raise ValueError("templates must be non-negative (Lemma 1)")
            col = np.zeros(self.N, dtype=np.uint64)
            for x, post in enumerate(self.postings):
                col[x] = int(coeff[post].sum())
            field.check_magnitude([int(col.max())])
            self.templates[name] = coeff
            self.A[name] = col
        field.check_magnitude(self.values)
        self.delta_rows = row_mac_keys(self.K_rowmac, self.N)
        self.masked_index = self._masked_index() if build_masked_index else None

    # -- fast path ---------------------------------------------------------
    def fast_layout(self, names, mac="row"):
        k = 1 << max(0, (len(names) - 1).bit_length())
        seg = self.bfv.half // k
        return FastLayout(list(names), seg, -(-self.N // seg), mac)

    def _mac_col(self, name, mac):
        a = self.A[name]
        if mac == "row":
            return field.mul(a, self.delta_rows)
        return field.mul(a, np.uint64(self.delta))

    def fast_columns(self, layout):
        H, seg = self.bfv.half, layout.seg
        cts = []
        for c in range(layout.chunks):
            lo, hi = c * seg, min((c + 1) * seg, self.N)
            v = np.zeros(self.bfv.slots, dtype=np.uint64)
            for r, name in enumerate(layout.templates):
                v[r * seg: r * seg + hi - lo] = self.A[name][lo:hi]
                v[H + r * seg: H + r * seg + hi - lo] = self._mac_col(name, layout.mac)[lo:hi]
            cts.append(self.bfv.encrypt(v))
        return cts

    def legacy_columns(self, name):
        L = self.bfv.slots
        val, mac = [], []
        macc = self._mac_col(name, "global")
        for lo in range(0, self.N, L):
            val.append(self.bfv.encrypt(self.A[name][lo:lo + L]))
            mac.append(self.bfv.encrypt(macc[lo:lo + L]))
        return val, mac

    # -- retrieval and flexible path -----------------------------------------
    def _masked_index(self):
        I = np.zeros((self.N, self.Nd), dtype=np.uint64)
        for x, post in enumerate(self.postings):
            I[x, post] = 1
        for x in range(self.N):
            I[x] = field.add(I[x], prg.uniform_zp(self.K_mask, prg.DOMAIN_MASK, x, self.Nd))
        return I

    def record_columns(self):
        """Record field m_i in row 0 and delta*m_i in row 1, H records per ct."""
        H = self.bfv.half
        m = self.values.astype(np.uint64)
        mm = field.mul(m, np.uint64(self.delta))
        cts = []
        for lo in range(0, self.Nd, H):
            v = np.zeros(self.bfv.slots, dtype=np.uint64)
            v[:len(m[lo:lo + H])] = m[lo:lo + H]
            v[H:H + len(mm[lo:lo + H])] = mm[lo:lo + H]
            cts.append(self.bfv.encrypt(v))
        return cts

    # -- outsourcing ---------------------------------------------------------
    def bundle(self, layouts=(), legacy=(), flexible=False):
        b = ProviderBundle(self.bfv.public_view(), self.N, self.Nd)
        for name, layout in layouts:
            b.fast[name] = (layout, self.fast_columns(layout))
        for name in legacy:
            b.legacy[name] = self.legacy_columns(name)
        if flexible:
            if self.masked_index is None:
                self.masked_index = self._masked_index()
            b.masked_index = self.masked_index
            b.records = self.record_columns()
        return b

    def user(self):
        """Authorised data user: dictionary, mask key, MAC keys, delegated sk."""
        return DataUser(self.bfv, self.D, self.N, self.Nd, self.n, self.K_mask,
                        self.delta, self.delta_rows, int(self.values.max(initial=0)))


@dataclass
class ProviderBundle:
    """The replicated, public half of a deployment. Holds no secret key."""
    he: object
    N: int
    Nd: int
    fast: dict = dc_field(default_factory=dict)
    legacy: dict = dc_field(default_factory=dict)
    masked_index: object = None
    records: list = None


# ---------------------------------------------------------------------------
# cloud provider
# ---------------------------------------------------------------------------
class Provider:
    def __init__(self, j, bundle):
        self.j = j
        self.b = bundle
        self.cc = bundle.he.cc

    @staticmethod
    def check_key(key, N):
        # Shape check only: a provider cannot check which row a hidden query
        # reads (Section 6.8 of the revised manuscript).
        if key.N != N:
            raise ValueError("key domain does not match the deployment")

    def _fast_plain(self, e, layout, c):
        H, seg = self.b.he.half, layout.seg
        lo, hi = c * seg, min((c + 1) * seg, self.b.N)
        v = np.zeros(self.b.he.slots, dtype=np.uint64)
        for r in range(len(layout.templates)):
            v[r * seg: r * seg + hi - lo] = e[lo:hi]
            v[H + r * seg: H + r * seg + hi - lo] = e[lo:hi]
        return self.b.he.encode(v)

    def fast(self, key, name, compress=False, e=None):
        """One ciphertext for all templates of layout `name`."""
        self.check_key(key, self.b.N)
        layout, cols = self.b.fast[name]
        if e is None:
            e = key.eval_full()
        acc = None
        for c, ct in enumerate(cols):
            acc = he.add(self.cc, acc, self.cc.EvalMult(ct, self._fast_plain(e, layout, c)))
        acc = he.segment_sum(self.cc, acc, layout.seg)
        return he.compress(self.cc, acc) if compress else acc

    def fast_legacy(self, key, name, e=None):
        """Submitted layout: value and MAC ciphertexts, each summed over all
        slots."""
        self.check_key(key, self.b.N)
        val, mac = self.b.legacy[name]
        if e is None:
            e = key.eval_full()
        L = self.b.he.slots
        out = []
        for col in (val, mac):
            acc = None
            for c, ct in enumerate(col):
                acc = he.add(self.cc, acc, self.cc.EvalMult(ct, self.b.he.encode(e[c * L:(c + 1) * L])))
            out.append(he.full_sum(self.cc, acc, L))
        return out

    def retrieve(self, key):
        self.check_key(key, self.b.N)
        return matvec_mod(key.eval_full(), self.b.masked_index)

    def contract(self, share_key, compress=False):
        """Flexible path, round 2: contract a share of the user's selection
        vector against the encrypted record column."""
        if share_key.N != self.b.Nd:
            raise ValueError("share length does not match the record count")
        v = share_key.eval_full()
        H = self.b.he.half
        acc = None
        for c, ct in enumerate(self.b.records):
            seg = v[c * H:(c + 1) * H]
            pv = np.zeros(self.b.he.slots, dtype=np.uint64)
            pv[:len(seg)] = seg
            pv[H:H + len(seg)] = seg
            acc = he.add(self.cc, acc, self.cc.EvalMult(ct, self.b.he.encode(pv)))
        acc = he.segment_sum(self.cc, acc, H)
        return he.compress(self.cc, acc) if compress else acc


# ---------------------------------------------------------------------------
# data user
# ---------------------------------------------------------------------------
class VerificationError(Exception):
    pass


class DataUser:
    def __init__(self, bfv, D, N, Nd, n, K_mask, delta, delta_rows, m_max):
        self.bfv = bfv
        self.m_max = m_max      # public bound on the record field, for Lemma 1
        self._sk = bfv.secret_key()
        self.D, self.N, self.Nd, self.n = D, N, Nd, n
        self.K_mask, self.delta, self.delta_rows = K_mask, delta, delta_rows

    def token(self, tag):
        return dpf.gen(self.D[tag], self.N, self.n)

    def _combine(self, cts):
        acc = cts[0]
        for ct in cts[1:]:
            acc = self.bfv.cc.EvalAdd(acc, ct)
        return self.bfv.decrypt(self._sk, acc)

    def finish_fast(self, tag, layout, responses):
        """Combine the n responses, check every template's MAC, decode."""
        alpha = self.D[tag]
        slots = self._combine(responses)
        H, seg = self.bfv.half, layout.seg
        out = {}
        for r, name in enumerate(layout.templates):
            y, yhat = int(slots[r * seg]), int(slots[H + r * seg])
            key = int(self.delta_rows[alpha]) if layout.mac == "row" else self.delta
            if yhat != y * key % field.P:
                raise VerificationError(f"MAC check failed for template {name}")
            out[name] = y
        return out

    def finish_legacy(self, responses):
        vals = self._combine([r[0] for r in responses])
        macs = self._combine([r[1] for r in responses])
        y, yhat = int(vals[0]), int(macs[0])
        if yhat != y * self.delta % field.P:
            raise VerificationError("MAC check failed")
        return y

    def finish_retrieve(self, tag, shares):
        alpha = self.D[tag]
        acc = shares[0]
        for s in shares[1:]:
            acc = field.add(acc, s)
        b = field.sub(acc, prg.uniform_zp(self.K_mask, prg.DOMAIN_MASK, alpha, self.Nd))
        if not np.isin(b, (0, 1)).all():
            raise VerificationError("retrieved row is not a 0/1 vector")
        return np.flatnonzero(b)

    def deal_selection(self, selection, weights=None):
        """Flexible path, round 2: fresh additive shares of w o 1_S."""
        v = np.zeros(self.Nd, dtype=np.uint64)
        sel = np.asarray(selection, dtype=np.int64)
        w = np.ones(len(sel), dtype=np.int64) if weights is None else np.asarray(weights, dtype=np.int64)[sel]
        if (w < 0).any():
            raise ValueError("weights must be non-negative (Lemma 1)")
        field.check_magnitude([int(w.sum()) * self.m_max])
        v[sel] = w.astype(np.uint64) % np.uint64(field.P)
        return dpf.share_vector(v, self.n)

    def finish_contract(self, responses):
        slots = self._combine(responses)
        y, yhat = int(slots[0]), int(slots[self.bfv.half])
        if yhat != y * self.delta % field.P:
            raise VerificationError("MAC check failed")
        return y
