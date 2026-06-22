# CR-SHE prototype (research artifact)

Correct, reproducible prototype of the CR-SHE search + homomorphic-aggregate pipeline.

## Files
- `dpf.py`   : two-party BGI-style DPF (GGM tree, SHA-based PRG). Exhaustively tested.
- `crshe.py` : pseudonymous index, DPF-based private search, Paillier aggregates.
- `bench.py` : benchmark harness; writes results.json + search_latency.pdf/png.
- `results.json` : the measured numbers used in the paper tables.

## Run
    pip install phe pycryptodome numpy matplotlib
    python3 dpf.py        # correctness
    python3 crshe.py      # end-to-end correctness
    python3 bench.py      # benchmarks + figure

## Honest scope / threats to validity
- DPF PRG is pure-Python SHA-512 (NOT AES-NI). A production AES-NI DPF is ~2-3 orders
  of magnitude faster per evaluation; the absolute search latencies here are
  Python+SHA artifacts, not the construction's intrinsic cost.
- The "pure-FHE proxy" charges ONE Paillier addition per item, which UNDER-states a
  real homomorphic equality scan (many ops/item). It is a generous lower bound for FHE.
- Two providers only (n=2). n>2 needs a multiparty DPF (future work).
- Synthetic index; the paper's full evaluation should use Enron + a real IoT dataset.
The prototype substantiates: correctness, linear-in-N symmetric search, succinct
O(lambda log N) keys, and feasible homomorphic aggregates. It does NOT yet substantiate
the headline "faster than FHE" claim; that needs the AES-NI DPF and a real FHE baseline.

## Real-dataset evaluation (added)
- `dataset_bench.py` runs the full evaluation on the real Reuters-21578 corpus
  (downloaded via NLTK): builds the keyword index + posting lists, uses each
  document's token count as a real numeric field, and emits four figures
  (`fig_search_latency`, `fig_compute_latency`, `fig_communication`,
  `fig_posting_cdf`) plus `results_real.json`.
- Run:  `pip install nltk`  then  `python3 dataset_bench.py`
  (first run downloads the `reuters` corpus from raw.githubusercontent.com).
