# Design decisions, and what this artefact does not do

Written so that the paper can be accurate about the prototype. Where the
implementation is weaker than the construction, that is said here plainly
rather than left for a reviewer to find.

## Parameters

| Choice | Value | Why |
|---|---|---|
| plaintext modulus `p` | 68724326401 (prime, ≈2^36.0) | `p ≡ 1 (mod 131072)`, so BFV batching works at every ring dimension up to 65536. Measured 75.6× headroom over the largest admissible aggregate of the primary corpus (908,575,470). |
| DPF output group | `Z_p`, the *same* `p` | Lemma 1. See below. |
| BFV depth | 1 | One plaintext–ciphertext product. `test_he` checks the worst case. |
| ring dimension | chosen by OpenFHE for 128-bit classical security | Overridable with `--ringdim`, which bypasses the library's security check; `security_bits` is then reported negated in the CSVs so a forced run is visible. |
| DPF PRG | fixed-key AES-128, MMO, three keys | The v1 prototype used SHA-512, which costs two to three orders of magnitude more per tree node. |

`Modulus` is the only place a modulus is defined, and the DPF, the index mask
and the HE backend all take it from there. Lemma 1's failure mode —
instantiating the DPF over `Z_{2^k}` and the homomorphic scheme over an
unrelated plaintext modulus — is data-dependent and easy to miss in testing, so
the code makes it unrepresentable rather than merely documented.

## The n-party DPF is not the succinct one

For `n = 2` this is the Boyle–Gilboa–Ishai GGM-tree DPF, keys `O(λ log N)`,
full-domain evaluation in one traversal (~3N AES calls, *not* N independent
`Eval` calls at `O(N log N)`).

For `n > 2` the paper needs `(n−1)`-privacy. Succinct multi-party DPFs exist —
BGI15 gives `O(2^{n/2} √N λ)` keys — but implementing one correctly is a
research-grade subproject, and shipping a subtly wrong one would invalidate
every number downstream. So `DpfN` uses the straightforward construction
instead: parties `1..n−1` hold a λ-bit seed whose counter-mode expansion is
their share, and one party holds the explicit difference vector. It is
correct by construction, `(n−1)`-private under the PRF assumption (a coalition
of any `n−1` parties is missing at least one seed expansion, which masks α),
and its uplink is *measured* rather than asserted: `N⌈log p⌉` bits for the
heavy party, 16 bytes for each of the others.

Measured on the real corpus (`N = 11,580`): 92,656 B for the heavy provider and
32 B for each of the others, so total uplink is 92,688 B at n=2 against 532 B
for the succinct two-party tree — a factor of 174. Which party is heavy is
public and query-independent, so rotating it across queries balances uplink
without affecting privacy.

**What the paper should say:** report the measured key sizes from
`e4_comm.csv`, state which construction produced them, and note that a succinct
`(n−1)`-private multi-party DPF would reduce the heavy key from `O(N log p)` to
`O(2^{n/2} √N λ)` — a real improvement this artefact does not implement. Do not
cite BGI15's asymptotics as though they were what was measured.

## Query authorisation is not implemented, and the attack is real

Section VI-F of the paper says providers "verify key well-formedness and
enforce a private access-control list before evaluating". This artefact does
not do that. `Dpf2::well_formed` checks the *shape* of a key — sizes, depth,
control bits in `{0,1}` — and nothing more, because nothing more is possible
from a single key: the correction words of a well-formed BGI16 key are
pseudorandom, so a key for a point function is indistinguishable from a key for
an arbitrary function.

`apps/attack_malformed_key.cpp` mounts the resulting attack against our own
provider: a client that submits shares of an arbitrary vector instead of a
point function receives an arbitrary linear combination of the masked index
rows, and `2N` such queries recover the entire index — after which the client,
which holds `K'`, strips the mask. The binary reports the recovery rate.

Closing this needs a verifiable DPF or a PACL-style non-interactive
authorisation proof. Note that the usual sketching-based well-formedness check
requires server-to-server communication, which this construction explicitly
forbids, so it is not a drop-in. **Section VI-F should state the requirement,
not claim it is met.**

## What the MAC detects

Two deviations, and the gap between them is Remark 4 of the paper:

* **inconsistent aggregate** — the provider returns a value ciphertext that is
  not the contraction its MAC ciphertext attests to. Caught except with
  probability `1/p`. Measured at 200/200 over 200 trials on the real corpus.
* **well-formed contraction against a different selection vector** — the
  provider evaluates a perfectly valid aggregate, just not the one asked for,
  in *both* the value and the MAC column. Then `ct_mac = δ·ct` still holds and
  the check passes. Measured at 0/200, as it must be.

`bench_verify` reports both. Reporting only the first would overclaim. Note
also that a perturbation at a tag with an empty posting list does not change
the aggregate at all, so it is not a deviation and is excluded from the
denominator rather than scored as a miss.

## The general path's storage is a result, not an omission

The masked index is `N × N_d` elements of `Z_p`. On the real corpus that is
11,580 × 405,184 × 8 B = **37.5 GB per provider** (measured), replicated `n`
times, and 9.26 GB already at N_d = 10^5. This is not a defect:
it is the real cost of a fully general oblivious selection, and it is exactly
why the fast path exists.

`bench_agg` therefore measures the general path on subsampled record sets and
records, in the CSV, the size that would have been required at the sizes it
skipped. `Owner::build_masked_index` refuses with an explanatory message rather
than thrashing. Report the Θ(N·N_d) scaling from the subsampled points and the
storage blow-up as a measured limitation.

Measured storage expansion over a plaintext bitmap is exactly 64x, i.e. the
stored word width. With `p < 2^32` the index elements would fit in `uint32`,
halving this to 18.8 GB, at the cost of shrinking the Lemma 1 headroom (measured
at 75.6x on this corpus). The code uses `uint64`
throughout for simplicity; the trade-off is available and untaken.

## Baselines

Implemented in `include/crshe/baselines.hpp` and `apps/bench_baselines.cpp`,
each carrying its leakage in its own comment so a table entry cannot drift from
what the code does. Baseline (v) lives in its own binary,
`apps/bench_fhe_scan.cpp`, because it builds a deliberately depth-heavy BFV
context and a slow or aborted run there must not cost the other four their
rows; `plot_all.py` merges its CSV back into the baselines figure.

The homomorphic-scan baseline (v) is the one earlier work of ours got wrong by
charging a single homomorphic addition per item. Here it pays a homomorphic
*equality*: `eq(a,b) = 1 − (a−b)^{q−1}` by Fermat over a small plaintext prime
`q`, with digit decomposition when the tag domain exceeds `q`, at the
multiplicative depth that actually implies. One full batch of `ℓ` slots is
measured and the total is extrapolated by the batch count; both the measured
batch cost and the extrapolation factor go into the CSV, and the figure shades
extrapolated bars differently.

Path ORAM is the non-recursive variant with a client-side position map
(`Z = 4`). A keyword query costs one access per matched record plus one for the
index entry, so its cost grows with `|S|` where CR-SHE's does not — which is
the comparison that matters.

## The plaintext HE backend

`--he=plain` swaps BFV for a plaintext stand-in with the same algebra. It
exists so the end-to-end tests and the whole harness run on a machine without
OpenFHE. It provides no confidentiality, every benchmark refuses to run with it
unless `--allow-insecure-he` is passed, and rows produced that way are tagged
`he=plain`. Nothing from it belongs in the paper.

## Things measured rather than asserted

* DPF key size and total uplink per `n`, including the worst party rather than
  party 0 — the client waits on the slowest provider.
* Ciphertext sizes, from `serialize().size()`, not from a formula.
* That the aggregate downlink is byte-identical for the smallest and largest
  posting lists (`test_e2e`).
* PRF throughput for the index mask, in mask values per second (`e7_setup.csv`).
* The masked rows' distribution against uniform over `Z_p`, by chi-square
  (`leakage_attack.py`) — evidence for Theorem 1, not a substitute for it.

## Where the fast path's time actually goes

On the fast path the query is `O(N)` PRG calls plus `O(N/ℓ)` packed
ciphertext–plaintext products and `O(log ℓ)` rotations. At the corpus sizes
here the second term dominates: the DPF pass over `N = 15,347` is under a
millisecond, while the two homomorphic contractions (value column and MAC
column) plus their rotate-and-sum are tens of milliseconds.

Two consequences worth stating in the paper rather than leaving for a reviewer
to infer:

* **Core scaling of a single fast-path query is limited by the homomorphic
  half, not by the selection half.** `e8_e10_scale.csv` will show the DPF pass
  scaling with threads and the end-to-end query barely moving, because the
  `--threads` sweep controls our OpenMP regions and OpenFHE parallelises
  internally on its own terms. Throughput across concurrent clients (E10) is
  the number that scales, and it is the one a deployment cares about.
* **The MAC column doubles both the homomorphic work and the downlink**, since
  it is a second contraction of the same shape. `bench_verify` measures both
  halves rather than assuming the factor of two.
