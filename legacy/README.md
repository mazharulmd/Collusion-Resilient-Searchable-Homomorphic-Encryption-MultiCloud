# Legacy prototype (superseded)

This directory holds the first Python prototype of CR-SHE (Paillier + a 2-party
DPF over Z_{2^64}). It predates the FGCS manuscript and does **not** implement
the construction described there. It is kept only for history.

Known defects, which is why it must not be cited as the paper's artefact:

* Paillier is additively homomorphic, not leveled HE as the old README said.
* The DPF output group is Z_{2^64}, unrelated to the Paillier plaintext ring,
  which is exactly the composition error Lemma 1 of the manuscript warns about.
* Search results are a single 64-bit mask, so `dataset_bench.py` folds the
  10,788 Reuters documents into 64 buckets (`r % 64`).
* Keyword rows are `PRF mod 2^n` with no collision handling: 45-63% of keywords
  share a row, and their posting lists are merged.
* The benchmark scans `range(N)` instead of the full `2^n` domain, so at
  N = 10,000 about 39% of keywords are never reached.
* The aggregation is not oblivious: the matched set is selected in the clear
  before `he_aggregate` runs.
* The "pure-FHE proxy" is N x one Paillier addition, extrapolated, and the
  prototype is slower than it at every size.

The maintained implementation is the `crshe/` package at the repository root.
