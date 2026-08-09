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
                  plot_all.py          CSVs -> Figures/
bench/            run_all.sh, netem_wan.sh
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

# everything measurable on one machine (~2-4 h on 32 cores)
bench/run_all.sh data/telemetry.crshe
```

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

`bench/results/` holds the CSVs behind every number in the paper, measured on a
4-core Intel Xeon @2.10 GHz with 15 GB RAM, AES-NI, OpenFHE 1.2.3, BFV at
p = 68,724,326,401 (37-bit prime), ring dimension 8192, depth 1, 128-bit
classical security. Corpus: the real 405,184-record telemetry dataset, indexed
into 11,580 tags (posting lists: median 35, mean 314.9, max 404,702).

| Result | Measured |
|---|---|
| Fast-path aggregate, N_d = 10^3 … 4.05×10^5 | 31.6 – 46.0 ms, **flat in N_d** |
| General path, N_d = 10^3 → 5×10^4 | 87.3 → 361.3 ms (Θ(N·N_d)) |
| Aggregate downlink | 525,950 B/provider, identical for every \|S\| |
| Selection (DPF), N = 11,580 | 0.273 ms (1 core) / 0.158 ms (4 cores) |
| DPF key, n = 2 | 266 B per provider |
| Faithful FHE equality scan | 163.3 s/query — ~4,760× the fast path |
| DORY-style search only (no analytics) | 51.0 ms vs 41.4 ms for the full fast path |
| Leakage: unmasked index | **100%** of device/flag/sensor-band tags re-identified |
| Leakage: masked index | **0%**, at every level of auxiliary knowledge |
| MAC vs inconsistent aggregate | 200/200 detected |
| MAC vs wrong selection vector | 0/200 detected (the documented gap) |
| Malformed-key extraction | 512/512 rows recovered in 2N queries |
| Masked index at full scale | 37.5 GB per provider — why the fast path exists |

Not measured here, and not estimated: wide-area transport across real cloud
regions, Raspberry Pi ingest energy, and the general path beyond N_d = 5×10^4
(the masked index exceeds this machine's RAM). See `docs/RUNBOOK.md` phases 6–7.

## Datasets

* **Primary** — Environmental Sensor Telemetry, 405,184 MQTT messages from
  three Raspberry-Pi sensor arrays.
  <https://www.kaggle.com/datasets/garystafford/environmental-sensor-data-132k>
* **Second** — UCI Beijing Multi-Site Air-Quality, ~420k rows across 12 sites.
  `prepare_dataset.py beijing` supports it, but the reported results do not use
  it: it could not be fetched in the environment the measurements were taken in.
  Running it is the cheapest way to answer the "only three physical devices"
  objection.
  <https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data>

`prepare_dataset.py` prints the tag count, posting-length distribution and the
Lemma 1 magnitude check for whichever corpus you build; those are the numbers
the paper should quote.

## License

Apache-2.0.
