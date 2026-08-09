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

* **The masked index is ~50 GB per provider at full scale**
  (15,347 × 405,184 × 8 B). The general path is measured on subsampled record
  sets and the skipped sizes are recorded in the CSV. That cost is the reason
  the fast path exists.
* **The MAC does not detect everything.** It catches an inconsistent aggregate
  except with probability `1/p`, and it does not catch a well-formed
  contraction against a different selection vector. `bench_verify` reports both
  numbers.
* **Query authorisation is not implemented.** `attack_malformed_key` recovers
  the whole index in `2N` queries against our own provider. Closing it needs a
  verifiable DPF or a PACL-style proof; see [`docs/DESIGN.md`](docs/DESIGN.md).

## Datasets

* **Primary** — Environmental Sensor Telemetry, 405,184 MQTT messages from
  three Raspberry-Pi sensor arrays.
  <https://www.kaggle.com/datasets/garystafford/environmental-sensor-data-132k>
* **Second** — UCI Beijing Multi-Site Air-Quality, ~420k rows across 12 sites,
  added because the primary corpus has only three physical devices.
  <https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data>

`prepare_dataset.py` prints the tag count, posting-length distribution and the
Lemma 1 magnitude check for whichever corpus you build; those are the numbers
the paper should quote.

## License

Apache-2.0.
