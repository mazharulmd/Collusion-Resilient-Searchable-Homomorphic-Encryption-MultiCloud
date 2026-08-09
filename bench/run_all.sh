#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Every experiment the paper needs, except the two that cannot be run from one
# machine: E3 (real multi-cloud WAN) and the Raspberry Pi edge measurement.
# Both are driven separately -- see docs/RUNBOOK.md.
#
#   bench/run_all.sh [dataset.crshe]
#
# Each experiment writes one CSV into bench/results/, and one CSV feeds one
# figure.  Nothing here writes to the manuscript: the numbers go into CSVs, the
# figures are regenerated from the CSVs, and you copy values into the LaTeX by
# hand so that every number in the paper is one you have looked at.
set -euo pipefail

cd "$(dirname "$0")/.."
DATA="${1:-data/telemetry.crshe}"
OUT=bench/results
CORES="$(nproc)"
mkdir -p "$OUT"

if [ ! -f "$DATA" ]; then
    echo "dataset $DATA not found."
    echo "Build it first, e.g."
    echo "  python3 python/prepare_dataset.py telemetry path/to/iot_telemetry_data.csv --out $DATA"
    echo "or for a dry run of the whole harness:"
    echo "  python3 python/prepare_dataset.py synthetic --out $DATA"
    exit 1
fi

# Thread sweep: 1, then powers of two up to the core count.
THREADS=1
t=2
while [ "$t" -le "$CORES" ]; do THREADS="$THREADS,$t"; t=$((t * 2)); done
[ "$THREADS" = "${THREADS%,$CORES}" ] && THREADS="$THREADS,$CORES"

echo "=================================================================="
echo " CR-SHE full evaluation"
echo "   dataset : $DATA"
echo "   cores   : $CORES   (thread sweep: $THREADS)"
echo "   results : $OUT"
echo "=================================================================="

run() {
    echo
    echo "------ $1 ------"
    shift
    "$@"
}

# Correctness first. If any of these fail, stop: the measurements below would
# be measurements of something that does not compute the right answer.
run "correctness: DPF"  ./build/test_dpf
run "correctness: BFV"  ./build/test_he
run "correctness: end-to-end" \
    ./build/test_e2e --data="$DATA" --nd=5000 --trials=200 --gen-trials=20

run "E1  selection latency vs N" \
    ./build/bench_dpf --N=1000,10000,15347,100000,1000000 \
        --threads="$THREADS" --reps=11 --out="$OUT/e1_dpf.csv"

run "E4  key size and communication" \
    ./build/bench_comm --N=1000,10000,15347,100000,1000000 --n=2,3,4 \
        --nd=100000 --out="$OUT/e4_comm.csv"

run "E2  oblivious aggregation, fast vs general" \
    ./build/bench_agg --data="$DATA" --nd=1000,10000,100000,405184 \
        --reps=11 --out="$OUT/e2_agg.csv"

run "E5  baselines" \
    ./build/bench_baselines --data="$DATA" --nd=100000 --reps=11 \
        --out="$OUT/e5_baselines.csv"

# Slow by construction: a depth-16 BFV context. Wrapped in `timeout` so that a
# machine that cannot build it does not stall the rest of the sweep -- if it is
# killed, say so in the paper rather than quoting a partial number.
echo
echo "------ E5b faithful homomorphic equality scan (slow) ------"
timeout "${FHE_TIMEOUT:-7200}" ./build/bench_fhe_scan --data="$DATA" \
    --out="$OUT/e5_fhe_scan.csv" || \
    echo "  bench_fhe_scan did not finish within ${FHE_TIMEOUT:-7200}s; "\
         "report it as not completed rather than estimating it."

run "E7  setup, masking and precomputation cost" \
    ./build/bench_setup --data="$DATA" --nd=1000,10000,100000 \
        --out="$OUT/e7_setup.csv"

run "E8/E10 core scaling and throughput" \
    ./build/bench_scale --data="$DATA" --threads="$THREADS" \
        --clients="$THREADS" --seconds=10 --out="$OUT/e8_e10_scale.csv"

run "E9  dynamic ingest" \
    ./build/bench_ingest --data="$DATA" --B=256,1024,4096,16384 \
        --out="$OUT/e9_ingest.csv"

run "E11 verification cost and detection rate" \
    ./build/bench_verify --data="$DATA" --nd=100000 --trials=200 \
        --out="$OUT/e11_verify.csv"

run "E6a index statistics (real PRF over the whole index)" \
    ./build/dump_index_stats --data="$DATA" --out="$OUT/e6_index_stats.csv"

run "E6b leakage-abuse attack" \
    python3 python/leakage_attack.py --stats "$OUT/e6_index_stats.csv" \
        --out "$OUT/e6_leakage.csv"

run "VI-F malformed-key extraction" \
    ./build/attack_malformed_key --ntags=512 --nd=1024 \
        --out="$OUT/e12_malformed_key.csv"

run "figures" python3 python/plot_all.py --results "$OUT" --figs Figures

echo
echo "=================================================================="
echo " Done. CSVs in $OUT, figures in Figures/."
echo
echo " Still to run, and they cannot be faked:"
echo "   E3  real multi-cloud WAN      -> docs/RUNBOOK.md, phase 6"
echo "   E8b Raspberry Pi edge cost    -> docs/RUNBOOK.md, phase 7"
echo "   second corpus                 -> python/prepare_dataset.py beijing ..."
echo "=================================================================="
