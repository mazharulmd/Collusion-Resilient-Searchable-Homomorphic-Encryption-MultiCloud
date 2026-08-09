# CR-SHE runbook

Everything the paper marks `\TODO` maps to a command here. Work top to bottom:
phases 1–3 decide whether the paper exists, and everything after is
measurement. Do not touch the manuscript prose until phase 3 passes on the
real corpus.

Target machine for the timings quoted below: 32 cores, 64 GB, Ubuntu 24.04.

---

## Phase 0 — environment (about an hour)

```bash
scripts/setup_ubuntu.sh          # deps, and it tells you what AES you have
scripts/install_openfhe.sh       # ~20 min on 32 cores
export LD_LIBRARY_PATH="$HOME/.local/openfhe/lib:$LD_LIBRARY_PATH"

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH="$HOME/.local/openfhe"
cmake --build build -j"$(nproc)"
```

**Check the AES line that `setup_ubuntu.sh` prints before writing any numbers
down.** Oracle's "OCPU" is not a vendor: `VM.Standard.A1` is Ampere/ARM and uses
ARMv8 crypto extensions; `E4`/`E5` are AMD x86 with AES-NI. Every binary prints
which path it took at startup, and every results CSV records it. If it says
*portable software AES*, the code is still correct but the throughput numbers
are worthless — fix the machine, do not report them.

## Phase 1 — DPF go/no-go (minutes)

```bash
./build/test_dpf
```

Exhaustive verification that the shares of every party sum to the point
function at every point of the domain, over Z_p, for depths up to 12, for
n ∈ {2,3,4,5}, plus the truncated non-power-of-two domain the real tag index
uses. If this does not pass, nothing downstream means anything.

```bash
./build/bench_dpf --N=1000,10000,15347,100000,1000000 --threads=1,8,16,32
```

## Phase 2 — BFV go/no-go (minutes)

```bash
./build/test_he
```

The case that matters is *full-magnitude Z_p coefficients*: on the general path
the plaintext multiplied into the ciphertext is a DPF share, hence uniform in
Z_p, which is the worst case for BFV noise. If it fails, raise `--depth` or
lower `--p`; do not lower the security level.

## Phase 3 — end-to-end go/no-go (an hour)

Build the corpus first.

```bash
# primary corpus
python3 python/prepare_dataset.py telemetry path/to/iot_telemetry_data.csv \
        --out data/telemetry.crshe

# second corpus, for the device-diversity concern
python3 python/prepare_dataset.py beijing path/to/PRSA_Data_dir \
        --out data/beijing.crshe
```

`prepare_dataset.py` prints the tag count, posting-list median/mean/max, and
the Lemma 1 magnitude check. Those are the corpus numbers the paper quotes —
take them from here, not from the earlier draft.

```bash
./build/test_e2e --data=data/telemetry.crshe --nd=5000 --trials=1000 --gen-trials=50
```

This is the real go/no-go: for a thousand random tags, on both paths and for
n ∈ {2,3,4}, the decrypted aggregate must equal the plaintext ground truth
exactly, retrieval must recover exactly the posting list, and the MAC must
verify. It also checks the two claims the security argument rests on: that the
aggregate downlink is byte-identical for the smallest and largest posting
lists, and what the MAC does and does not detect.

## Phases 4–5, 7–9 — everything measurable on one machine

```bash
bench/run_all.sh data/telemetry.crshe
```

Roughly two to four hours on 32 cores, dominated by E7 (the Θ(N·N_d)
precomputation) and E5 (the homomorphic-scan baseline, which builds a
depth-heavy BFV context on purpose). Then re-run against the second corpus with
a different results directory and compare.

The general path is skipped automatically at any N_d whose masked index does
not fit in RAM, and the skip is recorded in the CSV with the size that would
have been needed. **That refusal is a result.** At full scale the masked index
is 15,347 × 405,184 × 8 B ≈ 50 GB per provider, replicated n times. Report it
as the measured storage cost of a fully general oblivious selection, and as the
reason the fast path exists — not as a gap in the evaluation.

## Phase 6 — real multi-cloud deployment (E3)

This is the one experiment that cannot be run from a single box, and the one a
reviewer will check first.

```bash
# 1. On the data owner's machine
./build/crshe_setup --data=data/telemetry.crshe --bundle=deploy

# 2. Copy ONLY the public half to each provider instance
scp -r deploy/public  aws-eu:~/deploy/
scp -r deploy/public  gcp-us:~/deploy/
scp -r deploy/public  azure-ap:~/deploy/
#    deploy/secret/ holds sk and the MAC scalar; it never leaves the owner.

# 3. On each provider instance
./build/crshe_provider --bundle=~/deploy --port=9101

# 4. From the client
./build/crshe_client --bundle=deploy \
    --providers=aws-eu.example:9101,gcp-us.example:9101,azure-ap.example:9101 \
    --queries=200 --label="aws eu-west-1 / gcp us-central1 / azure ap-southeast-1" \
    --out=bench/results/e3_wan.csv
```

The client reports end-to-end latency decomposed into provider compute
(reported by the provider itself), wide-area transport (round-trip minus
compute), and client combine/decrypt, and separately measures bare RTT to each
provider with a ping frame so transport is not inferred only by subtraction.
Run once per n ∈ {2,3,4} by varying `--providers`.

Free-tier micro instances on AWS, GCP and Azure in three regions are enough:
the provider process holds only the fast-path columns, which are a few hundred
megabytes at full scale. If the free tiers cannot hold them, subsample with
`crshe_setup --nd=...` and say so.

If you genuinely cannot get three cloud accounts, measure the real inter-region
RTTs, reproduce them locally with `bench/netem_wan.sh`, and **state in the paper
that transport was emulated and where the RTT figures came from.** Documented
emulation is acceptable; silent emulation is not.

## Phase 7 — edge cost (E8b)

Borrow or buy a Raspberry Pi 4 or 5. This is what makes it an IoT-J paper
rather than a TIFS paper submitted to IoT-J, and a cgroup-throttled core is a
weak substitute.

```bash
# on the Pi, same build
./build/bench_setup --data=data/telemetry.crshe --nd=10000 \
    --out=bench/results/e8b_edge.csv
./build/bench_dpf --N=15347 --threads=1,4 --out=bench/results/e8b_edge_dpf.csv
```

`bench_setup` reports the corpus encryption throughput, which is the ingest
number. For energy, put a USB power meter inline and record average draw over
a fixed-length ingest run; report joules per thousand records alongside the
throughput.

## Phase 10 — figures and the manuscript

```bash
python3 python/plot_all.py --results bench/results --figs Figures
```

Then replace the `\TODO` markers. The mapping:

| Paper marker | Source |
|---|---|
| §III DPF key growth for n>2 | `e4_comm.csv`, and `docs/DESIGN.md` on which construction is used |
| Fig. 1 (architecture) | redraw by hand: one ciphertext per provider, no second round |
| §VIII implementation params | banner of any binary + `he_params` column in every CSV |
| §VIII datasets | `prepare_dataset.py` output for both corpora |
| E1 Fig. 2, Table V | `e1_dpf.csv` |
| E2 Fig. 3, Table VI | `e2_agg.csv` |
| E3 | `e3_wan.csv` |
| E4 Fig. 4 | `e4_comm.csv` |
| baselines (i)–(v) | `e5_baselines.csv` |
| E6 leakage | `e6_leakage.csv`, `e6_index_stats.csv` |
| E7 masking overhead | `e7_setup.csv` |
| E8 edge | `e8b_edge.csv` |
| E9 ingest | `e9_ingest.csv` |
| E10 throughput | `e8_e10_scale.csv` |
| E11 verification | `e11_verify.csv` |
| §VI-F authorisation | `e12_malformed_key.csv` |
| Fig. 5 posting CDF | `e6_index_stats.csv` |

Two results you should report even though they are not flattering, because a
reviewer will find them anyway and they are load-bearing for the argument:

* the general path's 50 GB-per-provider masked index at full scale, which is
  what motivates the fast path;
* `e12_malformed_key.csv`, which shows that the well-formedness check the paper
  cites does not exist in this artefact and that 2N queries recover the index
  without it. Section VI-F should say what is required, not that it is done.
  See `docs/DESIGN.md`.
