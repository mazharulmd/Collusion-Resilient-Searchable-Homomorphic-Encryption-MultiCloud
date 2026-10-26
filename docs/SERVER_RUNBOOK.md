# What the authors need to run, and what to send back

Three jobs remain that cannot be done from the environment that built v5: the real corpora
cannot be downloaded there, there is no second machine, and the closest papers' full texts cannot
be opened. Everything below has been tested end to end on small inputs (fixture CSVs with the
published columns; a two-provider deployment over localhost).

## Job 1: real-corpus experiments (one Ubuntu server, about 2–4 hours)

Requirements: Ubuntu 22.04 or 24.04, Python 3.12 (`sudo apt install python3.12 python3.12-venv`),
16 GB RAM, 15 GB free disk.

```bash
git clone <this repository> crshe && cd crshe
git checkout claude/stoic-bohr-lf0t6v
bash scripts/run_server_experiments.sh          # add FULL=1 for the Beijing hourly cube
```

The script downloads the Beijing data from UCI itself. For the telemetry data it needs either a
Kaggle API token (`pip install kaggle`, put `kaggle.json` in `~/.kaggle/`) or the file placed by
hand at `data/raw/iot_telemetry_data.csv` (Kaggle: "Environmental Sensor Telemetry Data",
garystafford).

It runs, in order, and logs each step to `logs/`:

| Step | Script | What it settles in the paper |
|---|---|---|
| Unit tests | `pytest` | the code on your machine behaves as here (83 tests) |
| Corpus statistics | `bench/corpus_stats.py` | that the loaders rebuild N, N_d and postings exactly as the manuscript states (prints OK or MISMATCH) |
| Correctness | `bench/correctness.py` on both corpora | the open author item "run correctness on both real corpora" |
| Leakage attack with padding baselines | `bench/bench_leakage.py` on both corpora | the missing power-of-two and volume-hiding columns, and the leakage figure with the **rejection-sampled** mask (resolves the Theorem 1 coverage gap without touching the C++ code) |
| Range aggregation on real data | `bench/bench_range_real.py` (telemetry: device × minute × CO band; Beijing: site × day × PM2.5 band; optional site × hour) | the main gap: range results on the real corpora, including tamper trials on the real cubes |

At the end it writes `crshe_server_results_<host>_<date>.tar.gz`. **Send that file back.**
Please also say which CPU the server has; every result file records it automatically.

## Job 2: cross-region deployment (2 or 3 cloud VMs, about 1 hour)

This replaces the loopback-only deployment numbers. Use two provider VMs in **different cloud
regions** (ideally different providers, e.g. one AWS and one GCP or Azure), plus a client
machine: a third VM, or your Ubuntu server.

On the client machine (it holds the secret key):

```bash
. .venv/bin/activate
python scripts/deploy/owner_setup.py --out bundle            # synthetic cube with the real dimensions
# or, with the real data present:  --cube telemetry
scp -r bundle/provider  user@PROVIDER1:crshe/bundle_provider
scp -r bundle/provider  user@PROVIDER2:crshe/bundle_provider
```

On each provider VM (clone the repository, install as in Job 1, open TCP port 9101 to the
client's IP only):

```bash
. .venv/bin/activate
OMP_NUM_THREADS=1 python scripts/deploy/provider_server.py --bundle bundle_provider --port 9101
```

Back on the client:

```bash
python scripts/deploy/client_bench.py --client bundle/client \
   --providers PROVIDER1_IP:9101 PROVIDER2_IP:9101 --label cross_region --queries 50
```

Then repeat with both providers in the **same** region (`--label same_region`), so the paper can
separate network cost from computation. Each run writes `results/deploy_<label>.json`, with per-query
end-to-end latency, provider compute, transport, client cost, sizes, RTT and correctness. **Send
those files back**, with the regions and VM types used.

The provider server has no authentication or TLS. It is an experiment harness, so restrict the
port to the client's address.

## Job 3: papers to send (PDFs)

**Received 2026-10-26 and read:** Splinter, DORY, BGI16 (CCS'16), ARQ, PVODTE. Findings in
`docs/NOVELTY_SEARCH.md` (third round). **Still needed:** Obscure (full version), Hafiz et al.,
HADES; Hayata et al. and Waldo if available.

The proxy blocks arXiv, ePrint, NDSS, VLDB and PETS here, so every statement about these works
currently rests on abstracts and search summaries. In order of importance:

**Must have (they decide whether the novelty claim holds):**

1. **Obscure, full version.** P. Gupta et al., "Obscure: Information-Theoretically Secure,
   Oblivious, and Verifiable Aggregation Queries on Secret-Shared Outsourced Data", arXiv
   2004.13115 (TKDE 2020), and the PVLDB 2019 version. *Closest prior work: thresholds, number of
   servers, range support.*
2. **Hafiz et al.**, "Private Aggregate Queries to Untrusted Databases", NDSS 2024 (arXiv 2403.13296).
3. **HADES.** X. Liu et al., "HADES: Range-Filtered Private Aggregation on Public Data", PVLDB
   18(7) 2025 (ePrint 2024/1699).
4. **ARQ** (PoPETs 2022, encrypted range aggregate queries).
5. **Splinter.** F. Wang et al., NSDI 2017 (does it support range predicates?).

**Should have:**

6. Boyle, Gilboa, Ishai, "Function Secret Sharing: Improvements and Extensions", CCS 2016
   (the multi-dimensional interval construction, for the "why prefix sums" comparison).
7. J. Li et al., "Silent Guardians: Independent and Secure Decision Tree Evaluation Without Chatter"
   (PVODTE), IEEE TDSC 2026 (closest to the tamper-evidence check).
8. Hayata et al., FSS-based PIR for range retrieval, IJIS 2020.
9. Waldo (IEEE S&P 2022) and DORY (OSDI 2020), to re-check the comparison table.

**Nice to have:** Choudhuri et al., "Homomorphic Secret Sharing with Verifiable Evaluation" (2024);
de Castro and Polychroniadou, verifiable FSS (Eurocrypt 2022); Servan-Schreiber et al., PACL
(S&P 2023); Ji et al., "Fine-grained Policy Constraints for DPF" (2023); Demertzis et al., TODS 2018.

With these the "?" cells of Table 1 can be filled in, the hedged sentences replaced with exact
statements, and the priority claim stated or withdrawn on evidence.

## What only the authors can do

* **C++ prototype (optional).** It is not in this repository. If you want its tables kept and
  updated (packed layout, rejection sampler), send the source; otherwise Job 1 lets the paper
  report masking and leakage from the reference implementation instead.
* **An outside reading of the proofs.** Theorem 2 (tamper evidence), Theorem 4 (leakage security)
  and Propositions 1–2, by a colleague who did not write them.
* **The AI-use declaration**: confirm it describes what you did.
* **Venue choice.** PoPETs needs the PETS template; TDSC the IEEE template.
