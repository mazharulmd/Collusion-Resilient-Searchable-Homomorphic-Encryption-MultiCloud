#!/usr/bin/env bash
# Run every experiment that needs the real corpora, then pack the results.
#
#   bash scripts/run_server_experiments.sh            # standard run (~2-4 h)
#   FULL=1 bash scripts/run_server_experiments.sh     # also the Beijing hourly cube (adds several hours, ~8 GB RAM)
#
# Needs: Ubuntu, Python 3.12, ~15 GB free disk, 16 GB RAM. Writes results/*.json and logs/*.log,
# and finally crshe_server_results_<host>_<date>.tar.gz to send back.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs data/raw
export OMP_NUM_THREADS=1          # the paper's reference figures are single-threaded

step() { echo; echo "=== $1"; }

step "Python environment"
PY=${PYTHON:-python3.12}
command -v "$PY" >/dev/null || { echo "need python3.12 (sudo apt install python3.12 python3.12-venv)"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

step "Datasets"
if [ ! -f data/raw/iot_telemetry_data.csv ]; then
  if command -v kaggle >/dev/null && [ -f ~/.kaggle/kaggle.json ]; then
    kaggle datasets download -d garystafford/environmental-sensor-data-132k -p data/raw --unzip
  else
    echo "MISSING data/raw/iot_telemetry_data.csv"
    echo "  Download 'Environmental Sensor Telemetry Data' (garystafford) from Kaggle and put"
    echo "  iot_telemetry_data.csv in data/raw/  (or: pip install kaggle, add ~/.kaggle/kaggle.json, re-run)"
    exit 1
  fi
fi
if ! ls data/raw/beijing/PRSA_Data_*_20130301-20170228.csv >/dev/null 2>&1; then
  mkdir -p data/raw/beijing /tmp/crshe_bj
  curl -fL -o /tmp/crshe_bj/bj.zip \
    "https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip"
  (cd /tmp/crshe_bj && unzip -o -q bj.zip && for z in *.zip; do [ "$z" = bj.zip ] || unzip -o -q "$z"; done)
  find /tmp/crshe_bj -name 'PRSA_Data_*_20130301-20170228.csv' -exec cp {} data/raw/beijing/ \;
fi
echo "telemetry: $(wc -l < data/raw/iot_telemetry_data.csv) lines; beijing files: $(ls data/raw/beijing | wc -l)"

step "Unit tests"
python -m pytest -q 2>&1 | tee logs/pytest.log | tail -2

cd bench
step "Corpus statistics (must match data/README.md)"
python corpus_stats.py 2>&1 | tee ../logs/corpus_stats.log
python - <<'PY'
import json
s = json.load(open("../results/corpus_stats.json"))
want = {"telemetry": (11580, 405184, 3646656), "beijing": (35162, 420370, 4624070)}
for k, (N, Nd, P) in want.items():
    got = (s[k]["N"], s[k]["Nd"], s[k]["postings"])
    print(k, "OK" if got == (N, Nd, P) else f"MISMATCH got {got}, manuscript says {(N, Nd, P)}")
PY

step "Correctness on the real corpora"
python correctness.py --corpus telemetry --nd 20000 --tags 200 2>&1 | tee ../logs/correctness_telemetry.log
python correctness.py --corpus beijing   --nd 20000 --tags 200 2>&1 | tee ../logs/correctness_beijing.log

step "Leakage attack: unmasked, power-of-two padded, volume-hiding, masked"
python bench_leakage.py --corpus telemetry 2>&1 | tee ../logs/leakage_telemetry.log
python bench_leakage.py --corpus beijing   2>&1 | tee ../logs/leakage_beijing.log

step "Range aggregation on the real corpora"
python bench_range_real.py --corpus telemetry                   2>&1 | tee ../logs/range_real_telemetry.log
python bench_range_real.py --corpus beijing --time day          2>&1 | tee ../logs/range_real_beijing_day.log
if [ "${FULL:-0}" = 1 ]; then
  python bench_range_real.py --corpus beijing --time hour --reps 3 --trials 10 2>&1 | tee ../logs/range_real_beijing_hour.log
fi
cd ..

step "Pack results"
out="crshe_server_results_$(hostname)_$(date +%Y%m%d_%H%M).tar.gz"
tar czf "$out" results logs
echo "Send back: $out"
