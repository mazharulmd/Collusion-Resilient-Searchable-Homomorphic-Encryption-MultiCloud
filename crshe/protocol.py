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

Verification
------------
global     row 1 holds delta * value under one owner key. Catches a response
           inconsistent with its tag, not a consistent linear substitution.
row        fast path only: per-row keys delta_x; catches substitutions except
           a rescaling of the hidden row itself.
session    row 1 holds a COPY of row 0, and the user sends a second set of
           keys (or shares) whose outputs are scaled by a fresh secret
           delta_s chosen per query, hidden by DPF privacy. The user checks
           yhat == delta_s * y. Any provider response that changes y is
           accepted with probability at most 1/p (plus the DPF advantage),
           whatever the provider computes, because its view is independent
           of delta_s. No MAC key is stored; costs twice the keys and DPF
           evaluation, no extra homomorphic work.

Roles
-----
An owner may assign every record to a role (record_role). A user of role r
gets only that role's mask key, so a retrieval reveals membership bits of
role-r records and nothing else (other words stay one-time-padded), and its
aggregate columns, cube tables and record column are built from role-r records
only. A provider serves a user only the columns of the user's role; that
policy check is the only thing a provider does, and it needs no interaction.
"""
import hashlib
import os
from dataclasses import dataclass, field as dc_field

import numpy as np

from . import dpf, field, he, prg

# Membership bits packed into one Z_p element of the masked index. p is just
# above 2^36, so 32 bits leave four bits of headroom: after the mask is
# stripped, a word >= 2^32 can only come from a corrupted share, and a random
# corruption lands below 2^32 with probability 1/16.
PACK_BITS = 32


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


def pack_row(post, words, bits=PACK_BITS):
    """Bit i of the row set for each record i in `post`, `bits` per word."""
    row = np.zeros(words, dtype=np.uint64)
    post = np.unique(np.asarray(post, dtype=np.int64))   # set semantics: a repeated id must not carry
    if len(post) and (post[0] < 0 or post[-1] >= words * bits):
        raise ValueError("record id outside the packed row")
    np.bitwise_or.at(row, post // bits, np.left_shift(np.uint64(1), (post % bits).astype(np.uint64)))
    return row


def unpack_row(row, n_records, bits=PACK_BITS):
    shifts = np.arange(bits, dtype=np.uint64)
    return ((row[:, None] >> shifts) & np.uint64(1)).reshape(-1)[:n_records]


def mask_rows(key, rows, n_records):
    """One-time-pad mask P[x] for each x in `rows`, exactly uniform on Z_p."""
    return np.stack([prg.uniform_zp(key, prg.DOMAIN_MASK, x, n_records) for x in rows])


def fresh_unit():
    """A uniformly random element of Z_p^*, the per-query session MAC key."""
    while True:
        d = int.from_bytes(os.urandom(8), "big") & ((1 << field.P_BITS) - 1)
        if 0 < d < field.P:
            return d


def role_key(key, role):
    """Mask key of one role, derived with keyed BLAKE2b (a PRF)."""
    return hashlib.blake2b(int(role).to_bytes(4, "big"), key=key, digest_size=16).digest()


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
    mac: str                # "row", "global" or "session"
    role: object = None     # None: all records


# ---------------------------------------------------------------------------
# data owner
# ---------------------------------------------------------------------------
class Owner:
    """Holds the plaintext records, the dictionary and every secret."""

    def __init__(self, tags, postings, values, templates, n, N=None, bfv=None,
                 seed=None, build_masked_index=False, pack_bits=PACK_BITS,
                 record_role=None):
        """
        tags       list of tag names; row of tag k is k (sorted order is the
                   caller's choice, rows never move)
        postings   list of int arrays, record ids carrying each tag
        values     computable field m_i, non-negative ints
        templates  dict name -> coefficient vector c_f[i] = w_f[i] * m_i
        n          number of providers
        N          tag domain (>= len(tags)); free rows are all-zero rows
        seed       fixes the owner's keys for reproducible experiments only
        pack_bits  membership bits per masked-index word (1 = one bit per
                   word, the unpacked layout)
        record_role  optional role id per record. Records of one packed
                   word must share a role, so that a role's mask key strips
                   whole words (lay records out by role, padded to words).
        """
        if not 1 <= pack_bits <= field.P_BITS - 1:
            raise ValueError("a packed word must stay below p")
        self.pack_bits = pack_bits
        self.tags = list(tags)
        self.D = {t: i for i, t in enumerate(self.tags)}
        self.postings = [np.asarray(p, dtype=np.int64) for p in postings]
        self.values = np.asarray(values, dtype=np.int64)
        self.Nd = len(self.values)
        for x, post in enumerate(self.postings):
            if len(post) and (post.min() < 0 or post.max() >= self.Nd):
                raise ValueError(f"posting list {x} names a record outside [0, N_d)")
            if len(np.unique(post)) != len(post):
                raise ValueError(f"posting list {x} repeats a record id")
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
        self.record_role = None if record_role is None else np.asarray(record_role, dtype=np.int64)
        self.word_role = None
        if self.record_role is not None:
            if len(self.record_role) != self.Nd:
                raise ValueError("one role per record")
            words = -(-self.Nd // self.pack_bits)
            self.word_role = np.empty(words, dtype=np.int64)
            for c in range(words):
                r = np.unique(self.record_role[c * self.pack_bits:(c + 1) * self.pack_bits])
                if len(r) != 1:
                    raise ValueError(f"packed word {c} mixes roles; align roles to {self.pack_bits} records")
                self.word_role[c] = r[0]
            self.roles = sorted(set(self.word_role.tolist()))
        self._role_cols = {}
        self.masked_index = self._masked_index() if build_masked_index else None

    # -- roles -------------------------------------------------------------
    def role_coeff(self, coeff, role):
        """A per-record coefficient vector restricted to one role's records."""
        coeff = np.asarray(coeff, dtype=np.int64)
        if role is None:
            return coeff
        return np.where(self.record_role == role, coeff, 0)

    def column(self, name, role=None):
        """A_f over all records, or over one role's records only."""
        if role is None:
            return self.A[name]
        if (name, role) not in self._role_cols:
            coeff = self.role_coeff(self.templates[name], role)
            col = np.zeros(self.N, dtype=np.uint64)
            for x, post in enumerate(self.postings):
                col[x] = int(coeff[post].sum())
            self._role_cols[(name, role)] = col
        return self._role_cols[(name, role)]

    def mask_row(self, x, words):
        """P[x]: one key for the whole row, or each word under its role's key."""
        if self.word_role is None:
            return prg.uniform_zp(self.K_mask, prg.DOMAIN_MASK, x, words)
        row = np.empty(words, dtype=np.uint64)
        for r in self.roles:
            sel = self.word_role == r
            row[sel] = prg.uniform_zp(role_key(self.K_mask, r), prg.DOMAIN_MASK, x, words)[sel]
        return row

    # -- fast path ---------------------------------------------------------
    def fast_layout(self, names, mac="row", role=None):
        k = 1 << max(0, (len(names) - 1).bit_length())
        seg = self.bfv.half // k
        return FastLayout(list(names), seg, -(-self.N // seg), mac, role)

    def _mac_col(self, name, mac, role=None):
        a = self.column(name, role)
        if mac == "session":
            return a                    # row 1 is a copy; the key rides in the query
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
                v[r * seg: r * seg + hi - lo] = self.column(name, layout.role)[lo:hi]
                v[H + r * seg: H + r * seg + hi - lo] = self._mac_col(name, layout.mac, layout.role)[lo:hi]
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
        """I'[x] = pack(I[x]) + P[x] mod p, `pack_bits` membership bits per word.
        A packed word is below 2^pack_bits < p, so the one-time pad still hides
        it perfectly (Theorem 1), and the index shrinks by pack_bits."""
        words = -(-self.Nd // self.pack_bits)
        I = np.zeros((self.N, words), dtype=np.uint64)
        for x, post in enumerate(self.postings):
            I[x] = pack_row(post, words, self.pack_bits)
        for x in range(self.N):
            I[x] = field.add(I[x], self.mask_row(x, words))
        return I

    def record_columns(self, mac="global", role=None):
        """Record field m_i in row 0 and, in row 1, delta*m_i (global MAC) or
        a copy of m_i (session MAC); H records per ciphertext. With a role,
        records outside it contribute zero."""
        H = self.bfv.half
        m = self.role_coeff(self.values, role).astype(np.uint64)
        mm = m if mac == "session" else field.mul(m, np.uint64(self.delta))
        cts = []
        for lo in range(0, self.Nd, H):
            v = np.zeros(self.bfv.slots, dtype=np.uint64)
            v[:len(m[lo:lo + H])] = m[lo:lo + H]
            v[H:H + len(mm[lo:lo + H])] = mm[lo:lo + H]
            cts.append(self.bfv.encrypt(v))
        return cts

    # -- outsourcing ---------------------------------------------------------
    def bundle(self, layouts=(), legacy=(), flexible=False, record_mac="global", role=None):
        b = ProviderBundle(self.bfv.public_view(), self.N, self.Nd)
        for name, layout in layouts:
            b.fast[name] = (layout, self.fast_columns(layout))
        for name in legacy:
            b.legacy[name] = self.legacy_columns(name)
        if flexible:
            if self.masked_index is None:
                self.masked_index = self._masked_index()
            b.masked_index = self.masked_index
            b.records = self.record_columns(record_mac, role)
        return b

    def user(self, role=None):
        """Authorised data user: dictionary, mask key(s), MAC keys, delegated
        sk. With roles, a user of role r holds only role r's mask key."""
        if self.word_role is None:
            if role is not None:
                raise ValueError("this deployment has no roles")
            mask = self.K_mask
        elif role is None:
            mask = {r: role_key(self.K_mask, r) for r in self.roles}
        else:
            mask = {role: role_key(self.K_mask, role)}
        return DataUser(self.bfv, self.D, self.N, self.Nd, self.n, mask,
                        self.delta, self.delta_rows, int(self.values.max(initial=0)),
                        self.pack_bits, self.word_role)


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

    def _fast_plain(self, e, layout, c, ehat=None):
        H, seg = self.b.he.half, layout.seg
        lo, hi = c * seg, min((c + 1) * seg, self.b.N)
        ehat = e if ehat is None else ehat
        v = np.zeros(self.b.he.slots, dtype=np.uint64)
        for r in range(len(layout.templates)):
            v[r * seg: r * seg + hi - lo] = e[lo:hi]
            v[H + r * seg: H + r * seg + hi - lo] = ehat[lo:hi]
        return self.b.he.encode(v)

    def fast(self, key, name, compress=False, e=None, key_hat=None, ehat=None):
        """One ciphertext for all templates of layout `name`. A session-MAC
        layout needs the second key, whose share goes into row 1."""
        self.check_key(key, self.b.N)
        layout, cols = self.b.fast[name]
        if e is None:
            e = key.eval_full()
        if layout.mac == "session" and ehat is None:
            if key_hat is None:
                raise ValueError("a session-MAC layout needs the second key")
            self.check_key(key_hat, self.b.N)
            ehat = key_hat.eval_full()
        acc = None
        for c, ct in enumerate(cols):
            acc = he.add(self.cc, acc, self.cc.EvalMult(ct, self._fast_plain(e, layout, c, ehat)))
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

    def retrieve(self, key, key_hat=None):
        """Masked-index row share. With a session key also the share of
        delta_s times the row, which the user checks word by word."""
        self.check_key(key, self.b.N)
        b = matvec_mod(key.eval_full(), self.b.masked_index)
        if key_hat is None:
            return b
        self.check_key(key_hat, self.b.N)
        return b, matvec_mod(key_hat.eval_full(), self.b.masked_index)

    def contract(self, share_key, compress=False, hat_key=None):
        """Flexible path, round 2: contract a share of the user's selection
        vector against the encrypted record column. With a session MAC the
        share of delta_s * v goes into row 1."""
        if share_key.N != self.b.Nd or (hat_key is not None and hat_key.N != self.b.Nd):
            raise ValueError("share length does not match the record count")
        v = share_key.eval_full()
        vh = v if hat_key is None else hat_key.eval_full()
        H = self.b.he.half
        acc = None
        for c, ct in enumerate(self.b.records):
            seg = v[c * H:(c + 1) * H]
            pv = np.zeros(self.b.he.slots, dtype=np.uint64)
            pv[:len(seg)] = seg
            pv[H:H + len(seg)] = vh[c * H:(c + 1) * H]
            acc = he.add(self.cc, acc, self.cc.EvalMult(ct, self.b.he.encode(pv)))
        acc = he.segment_sum(self.cc, acc, H)
        return he.compress(self.cc, acc) if compress else acc


# ---------------------------------------------------------------------------
# data user
# ---------------------------------------------------------------------------
class VerificationError(Exception):
    pass


class DataUser:
    def __init__(self, bfv, D, N, Nd, n, K_mask, delta, delta_rows, m_max,
                 pack_bits=PACK_BITS, word_role=None):
        self.bfv = bfv
        self.pack_bits = pack_bits
        self.word_role = word_role      # public layout: role of each packed word
        self.m_max = m_max      # public bound on the record field, for Lemma 1
        self._sk = bfv.secret_key()
        self.D, self.N, self.Nd, self.n = D, N, Nd, n
        self.K_mask, self.delta, self.delta_rows = K_mask, delta, delta_rows

    def token(self, tag):
        return dpf.gen(self.D[tag], self.N, self.n)

    def token_session(self, tag):
        """Keys for f_{alpha,1} and, independently, for f_{alpha,delta_s}
        with a fresh secret delta_s, which the user keeps."""
        ds = fresh_unit()
        a = self.D[tag]
        return dpf.gen(a, self.N, self.n), dpf.gen(a, self.N, self.n, beta=ds), ds

    def _combine(self, cts):
        acc = cts[0]
        for ct in cts[1:]:
            acc = self.bfv.cc.EvalAdd(acc, ct)
        return self.bfv.decrypt(self._sk, acc)

    def finish_fast(self, tag, layout, responses, delta_s=None):
        """Combine the n responses, check every template's MAC, decode."""
        alpha = self.D[tag]
        slots = self._combine(responses)
        H, seg = self.bfv.half, layout.seg
        if layout.mac == "session" and delta_s is None:
            raise ValueError("a session-MAC layout needs the query's delta_s")
        out = {}
        for r, name in enumerate(layout.templates):
            y, yhat = int(slots[r * seg]), int(slots[H + r * seg])
            key = {"row": lambda: int(self.delta_rows[alpha]), "session": lambda: delta_s,
                   "global": lambda: self.delta}[layout.mac]()
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

    def finish_retrieve(self, tag, shares, delta_s=None):
        """With delta_s, `shares` are (b_j, bhat_j) pairs and every word of the
        combined row must satisfy bhat == delta_s * b before unmasking."""
        alpha = self.D[tag]
        if delta_s is not None:
            hat = shares[0][1]
            for s in shares[1:]:
                hat = field.add(hat, s[1])
            shares = [s[0] for s in shares]
        acc = shares[0]
        for s in shares[1:]:
            acc = field.add(acc, s)
        if delta_s is not None and not np.array_equal(hat, field.mul(acc, np.uint64(delta_s))):
            raise VerificationError("retrieval check failed")
        words = -(-self.Nd // self.pack_bits)
        if self.word_role is None:
            known = np.ones(words, dtype=bool)
            row = field.sub(acc, prg.uniform_zp(self.K_mask, prg.DOMAIN_MASK, alpha, words))
        else:
            # strip only the words of roles whose key this user holds; the
            # others stay one-time-padded and are dropped
            known = np.zeros(words, dtype=bool)
            row = np.zeros(words, dtype=np.uint64)
            for r, k in self.K_mask.items():
                sel = self.word_role == r
                known |= sel
                row[sel] = field.sub(acc, prg.uniform_zp(k, prg.DOMAIN_MASK, alpha, words))[sel]
        if (row[known] >> np.uint64(self.pack_bits)).any():
            raise VerificationError("retrieved word exceeds the packed width")
        bits = unpack_row(row, words * self.pack_bits, self.pack_bits)
        if bits[self.Nd:].any():
            raise VerificationError("bits set beyond the record count")
        return np.flatnonzero(bits[:self.Nd])

    def deal_selection(self, selection, weights=None, session=False):
        """Flexible path, round 2: fresh additive shares of w o 1_S. With
        session=True also returns shares of delta_s * v and delta_s."""
        v = np.zeros(self.Nd, dtype=np.uint64)
        sel = np.asarray(selection, dtype=np.int64)
        w = np.ones(len(sel), dtype=np.int64) if weights is None else np.asarray(weights, dtype=np.int64)[sel]
        if (w < 0).any():
            raise ValueError("weights must be non-negative (Lemma 1)")
        field.check_magnitude([int(w.sum()) * self.m_max])
        v[sel] = w.astype(np.uint64) % np.uint64(field.P)
        if not session:
            return dpf.share_vector(v, self.n)
        ds = fresh_unit()
        return dpf.share_vector(v, self.n), dpf.share_vector(field.mul(v, np.uint64(ds)), self.n), ds

    def finish_contract(self, responses, delta_s=None):
        slots = self._combine(responses)
        y, yhat = int(slots[0]), int(slots[self.bfv.half])
        if yhat != y * (self.delta if delta_s is None else delta_s) % field.P:
            raise VerificationError("MAC check failed")
        return y
