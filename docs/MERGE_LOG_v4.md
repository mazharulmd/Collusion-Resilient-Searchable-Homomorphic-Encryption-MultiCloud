# How v4 was assembled from three drafts (2026-10-25)

> **Superseded in part by `docs/DRAFT_AUDIT_v4.md`**, which found that several draft-B numbers
> marked "no measurement found" below are in fact the authors' C++ results from the revision,
> and restored them (from the revision, not from draft B). Corrected rows are marked.

Inputs

| Draft | File | Origin (as stated by the author) | Basis |
|---|---|---|---|
| A | `paper/v3/CRSHE_v3.tex` | Claude session, after self-review (`docs/REVIEW_v3.md`) | range aggregation, packed index |
| B | `Cr_She_Upgraded_Manuscript.tex` (uploaded) | edited with ChatGPT and Gemini | the older single-keyword revision; **no range aggregation** |
| C | `CRSHE_v3_peer_review_working_draft.tex` (uploaded) | edited with ChatGPT and Gemini | draft A at commit c0788ed, with reviewer-style corrections |

Rule applied: every number in v4 is copied from a file in `results/` produced by a script in
`bench/`, or from the C++ measurements the earlier manuscripts already reported. A claim from B
or C that no file in this repository supports was either implemented and measured here, or left
out. Nothing below says B or C is wrong merely because it differs from A.

## Draft C (reviewer edits of v3): adopted unless noted

| Item | Decision |
|---|---|
| 4-template compressed time is 32.7 ms, not 35.4 ms (35.4 is the uncompressed row) | **Adopted**; it was an error in A |
| 1.8–2.9× is per provider; two providers sum to 47.0 and 62.8 ms, more than one single server | **Adopted**; A's wording invited the wrong reading |
| Two-party uplink in total is 520 / 588 B | **Adopted** |
| Loopback only; no wide-area increment can be inferred | **Adopted** |
| Duplicate posting IDs break additive bit packing | **Confirmed and fixed in code** (`pack_row` uses set semantics; `Owner` rejects duplicate or out-of-range IDs; regression test plus failure control) |
| Setup leakage must name layout, cube, tier metadata | **Adopted**, with role metadata added |
| Prefix-sum update rule for the newest time slice is unimplemented | **Adopted** as a stated limitation |
| Proposition 1 is only a counterexample to local linear answers | **Partly adopted**. The reduction to single-server PIR stays, because it is a valid argument once its two conditions (data-independent queries; correctness on every share tuple) are stated, which v4 now does. Its scope is narrowed to t = n−1, and a lower threshold escapes it |
| Lemma 3 holds only for non-adaptive share perturbations | **Superseded**: per-corner keys are replaced by the session-keyed check (Theorem 2, "Tamper evidence"), which covers arbitrary deviations and adaptive feedback |
| Combined layout has weaker integrity | **Resolved**: the verified (session) layout gives the combined layout full tamper evidence |
| Very defensive abstract and conclusion | **Not adopted verbatim**. v4 keeps the scope statements (synthetic cube, Python, per provider, computed baseline) inside an abstract that states the contribution |
| `\authorcheckstrue` in the build | Not adopted for the submission build; open items listed below |

## Draft B (upgraded manuscript): checked item by item

| Item in B | Evidence in this repository | Decision |
|---|---|---|
| "Selection-to-computation composition leak" naming | framing | **Adopted** |
| Three operational constraints (t = n−1, no server channel, owner encryption at rest) | framing | **Adopted** |
| Per-record "inverse-coupled" MAC on the flexible path | not implemented in B | **Idea adopted and generalised.** Implemented as the session-keyed check, which needs no per-record keys and covers every path (Theorem 2, `bench/bench_verify.py`) |
| HE-QAuth: per-role blinded columns, role-scoped mask keys | not implemented in B | **Idea adopted in corrected form** (role-filtered columns, tables and record column; mask keys per role over record words). B's per-tag key scoping cannot keep a role from reading other roles' records in an authorised tag's posting row, and B left the flexible path's record oracle open. Implemented, tested, measured (`bench/bench_roles.py`) |
| "0/512 unauthorised rows recovered" under HE-QAuth | no such run; the earlier measurement was **512/512 recovered without** a policy | **Replaced** by our own measurement |
| Z_{2^16} "modulus-decoupled" retrieval ring, 4× smaller index | not implemented; dominated by the 32-bit packing (32×) already in A | **Not adopted** |
| Corpus-2 general-path latencies (68.4–498.5 ms), OOM rows | **Correction (audit):** the real values are in the revision (106.3 … 382.0 ms; last two points refused by the harness). Draft B's values differ from them | **Measured values restored from the revision**; draft B's not used |
| BGI15 tensor keys for n > 2, 5,216 / 9,056 B, "18–31× less uplink" | not implemented; sizes from an unchecked formula | **Not adopted**; v4 keeps "succinct constructions exist; ours is non-succinct" |
| Emulated WAN, 25 ms RTT, 68.4–72.1 ms end to end | no run | **Not adopted** |
| Power-of-two and volume-hiding padding results (50–75 %, 2.27–9.11 %, inflation 1,272× / 465×) | `bench_leakage.py` exists but was never run on the real corpora (the proxy blocks the downloads); no result file | **Not adopted**; remains an author action |
| Canonical-embedding noise bound (Lemma "dual-ring") | formula not derived or checked here | **Not adopted**; v4 keeps the empirical worst-case check |
| LSM tiering with an O((τ/B) log(N_d/B)) amortised bound | not implemented | **Not adopted** |
| "24–108× client CPU" | from 14.6/0.54 and 67.5/0.62 the ratios are 27 and 109 | **Adopted as 27–109×** (audit) |
| "64-core engine: packing cuts 33.6 → 17.4 ms" | 33.6 ms is the C++ contraction alone (revision); 17.4 ms has no source | **Not adopted** |
| Corpus-2 throughput 117–124 q/s | **Correction (audit):** in the revision (C++) | **Adopted** |
| AI declaration "solely for language polishing" | inaccurate: AI tools wrote code, analysis and text | **Not adopted**; v4 names Claude, ChatGPT and Gemini and what each did, as far as the repository records it |

## New in v4 (this session)

* **Session-keyed tamper evidence** on the fast path, range (combined layout), flexible round and
  retrieval. Code: `crshe/protocol.py`, `crshe/rangeagg.py`. Tests: `tests/test_session_mac.py`,
  with failure controls (an attacker told δ_s passes; the global MAC misses the scaled share).
  Measured: `results/verification_modes.json`, `results/range_session.json`.
* **Role-scoped access**. Code: `crshe/protocol.py`. Tests: `tests/test_roles.py`, with failure
  controls (a single-key index unmasks every word; unfiltered columns leak other roles).
  Measured: `results/role_access.json`.
* **Packing bug fix** (from draft C).
* **Prior art, second round**: `docs/NOVELTY_SEARCH.md`. Obscure (PVLDB 2019, TKDE 2020) is the
  closest work found and is now cited and compared. The v3 sentence "none of them gives analytics
  … without inter-provider communication" is withdrawn.

## Still open before any submission

1. Read the full texts of Obscure, Hafiz et al., HADES, ARQ, Hayata et al. and PVODTE, and fill in
   the "?" cells of Table 1. If Obscure reaches t = n−1 with one-round range aggregates, re-scope.
2. Run range aggregation and `bench_leakage.py` (with padding baselines) on the real corpora.
3. Port range aggregation and the session check to C++; measure across cloud regions.
4. Have the proofs (Theorems 2 and 4, Propositions 1 and 2) read by someone outside the project.
5. The authors confirm the AI declaration.
