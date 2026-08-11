# CR-SHE

Reference implementation of **"CR-SHE: End-to-End Oblivious Keyword Search and
Analytics for Multi-Cloud IoT Data Sharing"** (submitted to IEEE Internet of
Things Journal).

Both keyword retrieval *and* analytics over the retrieved records are oblivious
to a coalition of up to `t = n−1` colluding cloud providers, over data
encrypted at rest under a single owner's key, with no communication between
providers. Each provider folds its distributed-point-function share directly
into the homomorphically encrypted record column and returns one ciphertext, so
the matched record set is never materialised at any provider and its
cardinality never leaves the client.

```
  client ──── one DPF key per provider ────▶  CP_1 ... CP_n
         ◀─── one ciphertext per provider ───
         combine, verify MAC, decrypt once
```

---

## Layout

```
include/crshe/    aes_prg    fixed-key AES-128 (AES-NI / ARMv8-CE / software)
                  zp         Z_p arithmetic; the single modulus (Lemma 1)
                  dpf        BGI16 two-party DPF + n-party (n−1)-private DPF
                  index      Setup / BuildIndex / Precompute (Algorithm 1)
                  he_backend BFV via OpenFHE, behind a narrow interface
                  protocol   Token / FastAgg / GenAgg / Retrieve / CombineDec
                  baselines  plaintext scan, SSE, Path ORAM
                  net        length-prefixed TCP for the multi-cloud deployment
src/              implementations
apps/             test_*     correctness go/no-gos
                  bench_*    one experiment each, one CSV each
                  attack_*   the leakage and malformed-key experiments
                  crshe_setup / crshe_provider / crshe_client   deployment
python/           prepare_dataset.py   raw CSV -> the binary corpus format
                  leakage_attack.py    E6
                  plot_all.py          CSVs -> Figures/<corpus>/
                  paper_numbers.py     CSVs -> LaTeX rows, and --check the paper
                  fig_architecture.py  Fig. 1
bench/            run_all.sh, run_local_deployment.sh, netem_wan.sh
bench/results/    one directory per corpus: telemetry/, beijing/
docs/             RUNBOOK.md   the phase-by-phase process
                  DESIGN.md    decisions, and what this artefact does not do
legacy/           the v1 pure-Python prototype, kept for provenance only
```

## Build

```bash
scripts/setup_ubuntu.sh                     # deps; prints which AES you have
scripts/install_openfhe.sh                  # ~20 min
export LD_LIBRARY_PATH="$HOME/.local/openfhe/lib:$LD_LIBRARY_PATH"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH="$HOME/.local/openfhe"
cmake --build build -j"$(nproc)"
```

Without OpenFHE the project still builds, but only the plaintext stand-in
backend is available and every benchmark refuses to emit HE numbers from it.

## Run

```bash
# correctness, in order. Each is a go/no-go for the next.
./build/test_dpf
./build/test_he
./build/test_e2e --data=data/telemetry.crshe --nd=5000 --trials=1000

# corpus
python3 python/prepare_dataset.py telemetry path/to/iot_telemetry_data.csv \
        --out data/telemetry.crshe
python3 python/prepare_dataset.py synthetic --out data/syn.crshe   # dry run

# everything measurable on one machine (~2-4 h on 32 cores).
# Give each corpus its own results and figures directory, or the second run
# overwrites the first.
bench/run_all.sh data/telemetry.crshe bench/results/telemetry Figures/telemetry
bench/run_all.sh data/beijing.crshe   bench/results/beijing   Figures/beijing
```

The sweeps are sized from the corpus itself -- the tag domain `N` and the record
count `N_d` are read out of the `.crshe` header -- so the domain sweep measures
the tag count the corpus actually has and the record sweep ends at the whole
corpus. Nothing is hard-coded to one dataset.

The last step of each run checks the manuscript against the CSVs
(`python/paper_numbers.py --check`). It is corpus-aware: the paper reports the
telemetry corpus in the selection and aggregate tables, and the Beijing corpus
in the second-corpus table, so each is checked against its own. A corpus the
paper does not report at all (a synthetic dry run, say) has its rows printed and
the check skipped rather than failed.

The real multi-cloud deployment (E3) and the Raspberry Pi edge measurement are
driven separately — see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Reading the output

Every binary prints its CPU, thread count, AES backend and HE parameters at
startup, and every results row repeats them, so a number can never be separated
from the machine it came from. One CSV feeds one figure; when a reviewer asks
how a figure was produced, the answer is one file and one command.

Three things the code deliberately reports against itself, because they are
load-bearing for the paper's argument:

* **The masked index is 37.5 GB per provider at full scale**
  (11,580 × 405,184 × 8 B, measured). The general path is measured on subsampled
  record sets and the skipped sizes are recorded in the CSV. That cost is the
  reason the fast path exists.
* **The MAC does not detect everything.** It catches an inconsistent aggregate
  except with probability `1/p`, and it does not catch a well-formed
  contraction against a different selection vector. `bench_verify` reports both
  numbers.
* **Query authorisation is not implemented.** `attack_malformed_key` recovers
  the whole index in `2N` queries against our own provider. Closing it needs a
  verifiable DPF or a PACL-style proof; see [`docs/DESIGN.md`](docs/DESIGN.md).

## Measured results

`bench/results/<corpus>/` holds the CSVs behind every number in the paper, and
`Figures/<corpus>/` the figures regenerated from them. The primary corpus is
`telemetry`, and the manuscript's figures point at `Figures/telemetry/`.
Measured on an **AMD EPYC 7J13, 64 cores, 64 GB, Ubuntu 24.04**, AES-NI, OpenFHE 1.2.3, BFV at
p = 68,724,326,401 (37-bit prime), ring dimension 8192, depth 1, 128-bit
classical security. Corpus: the real 405,184-record telemetry dataset, indexed
into 11,580 tags (posting lists: median 35, mean 314.9, max 404,702).

| Result | Measured |
|---|---|
| Fast-path aggregate, N_d = 10^3 … 4.05×10^5 | **38.8 – 39.2 ms, flat to ±0.5%** |
| General path, same range | 103.7 → **1378.2 ms** (35.5× the fast path) |
| Aggregate downlink | 525,950 B/provider, identical for every \|S\| |
| Selection (DPF), N = 11,580 | 0.336 ms (1 thread) → 0.177 ms (16) |
| DPF key, n = 2 | 266 B per provider; 532 B uplink |
| n-party heavy key, N = 11,580 | 92,656 B → 174× the two-party tree |
| Deployment, n = 2 → 4 | provider compute **flat**: 34.8 → 35.5 ms |
| Faithful FHE equality scan | 24.2 s/query — **617×** the fast path |
| DORY-style search only (no analytics) | 130.4 ms vs **39.2 ms** for the full fast path |
| Leakage: unmasked index | **100%** of device/flag/sensor-band tags re-identified |
| Leakage: masked index | **0%**, at every level of auxiliary knowledge |
| MAC vs inconsistent aggregate | 200/200 detected |
| MAC vs wrong selection vector | 0/200 detected (the documented gap) |
| Malformed-key extraction | 512/512 rows recovered in 2N queries |
| Masked index at full scale | 37.5 GB per provider — why the fast path exists |
| Throughput | 29 q/s (1 client) → plateau 122–128 q/s (16–64) |

Two measurement notes carried into the paper rather than smoothed over:

* The fast path's flatness is from an **order-controlled** sweep. A first sweep
  in increasing N_d showed the early points ~14 ms slower; because that step was
  *anti*-correlated with N_d, the sweep was repeated in decreasing order and
  reproduced 38.8–39.2 ms everywhere. Both runs are released
  (`e2_agg.csv`, `e2_fast_reversed.csv`).
* Selection peaks at 16–32 threads and **regresses** past that (N=10^6:
  18.8 ms at 32 threads, 24.4 ms at 64). Reported, not hidden.
* Sub-millisecond selection timings on this shared cloud host vary by up to
  ~25% between runs of the identical binary at N≈10^4; the N=10^6 figures
  repeat to within 1%. Medians of 21 runs, IQR in the CSV.

### Second corpus

The whole suite was re-run on the Beijing corpus below
(`bench/results/beijing/`, `Figures/beijing/`), on the same machine:

| Result | telemetry (N=11,580) | Beijing (N=35,162) |
|---|---|---|
| Fast-path aggregate | 38.8–39.2 ms | **40.2–41.2 ms** (+5% for 3.04× the tags) |
| General path at N_d = 10^5 | 196.8 ms | **382.0 ms**, 28.13 GB index |
| General path at full scale | 37.5 GB | **118.2 GB** — last two sweep points refused |
| Aggregate downlink | 525,950 B | 525,950 B, unchanged |
| DORY-style search only | 130.4 ms | **305.6 ms** (7.4× the fast path) |
| FHE equality scan | 24.2 s | 24.4 s (592× the fast path) |
| Leakage, unmasked | 100% per non-time class | **100%** in all ten non-time classes |
| Leakage, masked | 0% | **0%**, χ²=62.38 on 63 df, p=0.4986 |
| Deployment, n = 2 → 4 | 34.8 → 35.5 ms | **38.67 → 38.47 ms**, flat |
| Masked-index build, N_d = 10^5 | 5.6 s | 16.6 s (linear in N) |

One caveat on the released `bench/results/beijing/e1_dpf.csv` and `e4_comm.csv`:
they were measured before the sweep was derived from the corpus, so they cover
N = 11,580 -- the *primary* corpus's tag domain -- not Beijing's 35,162. The
paper therefore quotes no selection latency for this corpus. Re-running
`run_all.sh` now measures the right domain.

The point of the second corpus is the twelve monitoring sites: the primary
corpus has three physical devices, so a reader can reasonably ask whether the
leakage result depends on that. It does not — the site identifiers and the
wind-direction tags are re-identified at 100% from the unmasked index and 0%
from the masked one, exactly as the device identifiers are in the primary
corpus.

Not measured, and not estimated: wide-area transport across real cloud regions
(the deployment is single-host loopback) and Raspberry Pi ingest energy. See
`docs/RUNBOOK.md` phases 6–7.

## Datasets

* **Primary** — Environmental Sensor Telemetry, 405,184 MQTT messages from
  three Raspberry-Pi sensor arrays.
  <https://www.kaggle.com/datasets/garystafford/environmental-sensor-data-132k>
* **Second** — UCI Beijing Multi-Site Air-Quality, 420,768 hourly rows across
  **12 monitoring sites**, which is what answers the "only three physical
  devices" objection.
  <https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data>

  ```bash
  # Point the builder at the UCI zip directly -- it handles the nested archive.
  curl -L -o data/beijing.zip \
    "https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip"
  python3 python/prepare_dataset.py beijing data/beijing.zip --out data/beijing.crshe
  ```

  The outer zip contains an inner zip which contains the twelve CSVs; the
  builder accepts the outer zip, the inner zip, an extracted directory at
  either depth, or a single CSV, and all forms produce a byte-identical
  corpus.

  Yields **35,162 tags** over 4,624,070 postings (posting lengths: median 12,
  mean 131.5, max 102,344) and 420,370 records, 3x the tag domain of the
  primary corpus, and a **118.2 GB** masked index at full scale. This corpus
  has missing values, and they are handled explicitly rather than silently:
  a channel reading `NA` gets
  its own `<chan>:na` tag instead of being folded into the lowest quantile band
  (CO is NA in 4.9% of rows, so band-0 folding would have merged "sensor down"
  with "clean air"), and the 398 rows with a missing TEMP are dropped, because
  TEMP is the computable field and an aggregate must not sum an invented
  value.

`prepare_dataset.py` prints the tag count, posting-length distribution and the
Lemma 1 magnitude check for whichever corpus you build; those are the numbers
the paper should quote.

## License

Apache-2.0.
