# CR-SHE: oblivious homomorphic aggregation over encrypted multi-cloud IoT data

CR-SHE lets a data user search and aggregate IoT records that are replicated, encrypted
under one owner's key, across *n* independent clouds. No coalition of up to *n − 1*
providers learns which records matched, how many matched, or the result. The providers
never communicate with each other.

* A query is one distributed point function (DPF) key per provider.
* Each provider folds its share of the selection into encrypted columns and returns
  **one** BFV ciphertext.
* The user adds the *n* ciphertexts, checks a MAC, and decrypts once.

This repository holds the reference implementation, the experiments, the FGCS
submission and its revision.

## Status

| | |
|---|---|
| FGCS submission (FGCS-D-26-05016) | Rejected 27 Sep 2026, "results too premature". Package archived in [`paper/fgcs-2026-submission/`](paper/fgcs-2026-submission/) |
| Why, and what to do next | [`docs/REJECTION_ANALYSIS.md`](docs/REJECTION_ANALYSIS.md) |
| *Internet of Things* submission (IOT-D-26-03923) | Desk-rejected, "lack of sufficient novelty". Package in [`paper/iot-elsevier/`](paper/iot-elsevier/) |
| **JNCA submission (current)** | [`paper/jnca/submission/`](paper/jnca/submission/): Word manuscript (18 pages), highlights, competing-interests declaration, figures, supplementary material, checked against the guide for authors; see [`docs/JNCA_SUBMISSION.md`](docs/JNCA_SUBMISSION.md) |
| **v5 manuscript (full length)** | [`paper/v5/CRSHE_v5.pdf`](paper/v5/CRSHE_v5.pdf): a second round of ChatGPT/Gemini edits checked and corrected; audit in [`docs/DRAFT_AUDIT_v5.md`](docs/DRAFT_AUDIT_v5.md) |
| **Real-corpus results** | [`docs/SERVER_RESULTS_20261026.md`](docs/SERVER_RESULTS_20261026.md): what the authors' server run established, and why the C++ leakage figures were withdrawn |
| **What the authors still need to run** | [`docs/SERVER_RUNBOOK.md`](docs/SERVER_RUNBOOK.md): per-tag length dump, cross-region deployment (`scripts/deploy/`) |
| v4 manuscript | [`paper/v4/CRSHE_v4.pdf`](paper/v4/CRSHE_v4.pdf): v3 merged with two externally edited drafts; adds a per-query tamper-evidence check on every path and role-scoped access, both implemented and measured. What came from where: [`docs/MERGE_LOG_v4.md`](docs/MERGE_LOG_v4.md) |
| v3 manuscript | [`paper/v3/CRSHE_v3.pdf`](paper/v3/CRSHE_v3.pdf): adds oblivious range aggregation over encrypted data cubes and a bit-packed masked index. Prior-art search and its limits: [`docs/NOVELTY_SEARCH.md`](docs/NOVELTY_SEARCH.md) |
| Revised manuscript (FGCS response) | [`paper/revision/CRSHE_revised.pdf`](paper/revision/CRSHE_revised.pdf), tracked changes in [`CRSHE_diff.pdf`](paper/revision/CRSHE_diff.pdf), list of changes and open items in [`CHANGES.md`](paper/revision/CHANGES.md) |
| Reference implementation | [`crshe/`](crshe/), 83 tests in [`tests/`](tests/) |
| Experiments | [`bench/`](bench/) scripts → [`results/`](results/) JSON → tables generated into the manuscript |
| First Paillier prototype | [`legacy/`](legacy/). Superseded, kept for history, with its defects listed |

## Repository layout

```
crshe/            reference implementation (Python driving OpenFHE's C++ kernels)
  field.py        the single Z_p shared by DPF, mask and BFV (Lemma 1 by construction)
  prg.py          fixed-key AES-MMO generator; AES-CTR PRF with exact rejection sampling
  dpf.py          two-party BGI tree DPF over Z_p; non-succinct n-party sharing
  he.py           BFV at p = 68,724,326,401, ring 8,192, depth 1, 128-bit security
  protocol.py     owner / provider / data user: fast path, retrieval (bit-packed index), flexible path
  rangeagg.py     oblivious range aggregation: encrypted summed-area cubes, 2^d signed DPF keys
  baselines.py    single-server encrypted-selection baseline; (n,n)-sharing counterexample
  attack.py       frequency attack vs unmasked, padded, volume-hiding and masked index
  corpus.py       loaders for the two public IoT corpora, plus a synthetic corpus
tests/            pytest suite
bench/            one script per experiment; make_tables.py renders results into LaTeX
results/          JSON outputs, each stamped with the machine and library versions
data/             where the raw corpora go (not redistributed; see data/README.md)
paper/            FGCS and IoT submissions (as submitted), the revision, and v3
docs/             rejection analysis and revision plan
legacy/           superseded Paillier prototype
```

## Quick start

The OpenFHE wheel used here is built for **CPython 3.12 on Linux x86-64**.

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q                                   # 83 tests

cd bench
OMP_NUM_THREADS=1 python bench_response.py  # packing, compression, single-server baseline
python bench_mac.py                         # MAC detection, global vs per-row keys
OMP_NUM_THREADS=1 python bench_flexible.py --nd 20000 10000 5000 1000
OMP_NUM_THREADS=1 python bench_ops.py       # per-op costs, single-server retrieval bound
OMP_NUM_THREADS=1 python bench_range.py     # range aggregation over a synthetic telemetry-shaped cube
OMP_NUM_THREADS=1 python bench_packed.py    # masked index, 1 vs 32 bits per word
OMP_NUM_THREADS=1 python bench_verify.py    # what each verification mode catches, every path
OMP_NUM_THREADS=1 python bench_roles.py     # index extraction with and without role-scoped keys
python make_tables.py                       # regenerate paper/{revision,v3,v4}/tables/*.tex

# these need the raw corpora in data/raw/ (see data/README.md)
python corpus_stats.py
python correctness.py --corpus telemetry
python bench_leakage.py --corpus telemetry
```

A minimal end-to-end query:

```python
import numpy as np
from crshe import Owner, Provider

values = np.array([2150, 2230, 1990, 2410])           # e.g. temperature x 100
postings = [np.array([0, 2]), np.array([1, 2, 3])]    # records carrying each tag
owner = Owner(["device:a", "device:b"], postings, values,
              {"count": np.ones(4, int), "sum": values}, n=2)
layout = owner.fast_layout(["count", "sum"])
bundle = owner.bundle(layouts=[("stats", layout)])    # replicated to every provider
providers = [Provider(j, bundle) for j in range(2)]
user = owner.user()

keys = user.token("device:b")
print(user.finish_fast("device:b", layout, [p.fast(k, "stats", compress=True)
                                            for p, k in zip(providers, keys)]))
# {'count': 3, 'sum': 6630}: one 132 kB ciphertext per provider
```

## Headline numbers (reference implementation, one thread, 4-vCPU Xeon VM)

| | Submitted layout | Revised (packed + compressed) |
|---|---:|---:|
| Fast path, 1 template, N = 11,580 tags | 53.0 ms, 526,022 B | 27.0 ms, 132,081 B |
| Fast path, 4 templates | 194.9 ms, 2,104,088 B | 32.7 ms, 132,081 B |
| Single server on the same columns (no non-collusion assumption) | | 42.6 ms server, 789,033 B uplink |

The trust split's advantage over a single server is a small constant factor in server
work. It is large in uplink and client cost: a 260 B DPF key against 3–9 fresh
ciphertexts. See §10.5 of the revised manuscript.

Range aggregation (v3; synthetic cube of 3 × 11,523 × 10 cells, 405,184 records): the client
sends 8 DPF keys, 2,760 B in total, for any 3-D box, and gets one 132,081 B ciphertext per
provider, whatever the window length (1 to 11,523 time steps). A single server answering the
same query would need an encrypted selector as long as the cube, 44,448,859 B (computed).
Provider time is 0.8–0.9 s (combined layout) or 3.2–3.4 s (per-corner MAC layout) in Python.
The bit-packed masked index is 32× smaller (1.17 GB vs 37.5 GB computed at 405,184 records).

Tamper evidence (v4): with a per-query secret scalar carried in a second key set, no wrong answer
was accepted in 4,000 tampered queries over the fast, range, flexible and retrieval paths; one
stored MAC key accepted every consistent substitution, and per-row/per-cell keys missed every
deviation aimed at the queried point. The verified range layout costs 1.40–1.53 s per provider
(combined layout 0.78–0.91 s). Role-scoped keys: a role-0 user recovered 0 of 365,227 other-role
membership bits, against all of them with one mask key. The C++ prototype the manuscript's
other tables come from is not yet in this repository.

## Licence

No licence has been chosen yet. Until one is added, all rights are reserved by the
authors.
