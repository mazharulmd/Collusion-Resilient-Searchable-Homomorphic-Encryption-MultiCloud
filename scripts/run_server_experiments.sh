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
command -v unzip >/dev/null || { echo "need unzip (sudo apt install unzip)"; exit 1; }
KSLUG=garystafford/environmental-sensor-data-132k
if [ ! -f data/raw/iot_telemetry_data.csv ]; then
  # credentials from ~/.kaggle/kaggle.json, or KAGGLE_USERNAME / KAGGLE_KEY in the environment
  if [ -z "${KAGGLE_USERNAME:-}" ] && [ -f ~/.kaggle/kaggle.json ]; then
    KAGGLE_USERNAME=$(python -c 'import json,os;print(json.load(open(os.path.expanduser("~/.kaggle/kaggle.json")))["username"])')
    KAGGLE_KEY=$(python -c 'import json,os;print(json.load(open(os.path.expanduser("~/.kaggle/kaggle.json")))["key"])')
  fi
  if [ -n "${KAGGLE_USERNAME:-}" ] && [ -n "${KAGGLE_KEY:-}" ]; then
    curl -fL -u "$KAGGLE_USERNAME:$KAGGLE_KEY" -o /tmp/crshe_tel.zip \
      "https://www.kaggle.com/api/v1/datasets/download/$KSLUG" \
      && unzip -o -q /tmp/crshe_tel.zip -d data/raw || echo "Kaggle download failed"
  fi
fi
if ! ls data/raw/beijing/PRSA_Data_*_20130301-20170228.csv >/dev/null 2>&1; then
  mkdir -p data/raw/beijing /tmp/crshe_bj
  curl -fL -o /tmp/crshe_bj/bj.zip \
    "https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip" \
    && (cd /tmp/crshe_bj && unzip -o -q bj.zip && for z in *.zip; do [ "$z" = bj.zip ] || unzip -o -q "$z"; done) \
    && find /tmp/crshe_bj -name 'PRSA_Data_*_20130301-20170228.csv' -exec cp {} data/raw/beijing/ \; \
    || echo "UCI download failed"
fi
CORPORA=""
if [ -f data/raw/iot_telemetry_data.csv ]; then
  CORPORA="$CORPORA telemetry"; echo "telemetry: $(wc -l < data/raw/iot_telemetry_data.csv) lines (405,185 expected with header)"
else
  echo "SKIPPING telemetry: data/raw/iot_telemetry_data.csv is missing."
  echo "  Get it from https://www.kaggle.com/datasets/$KSLUG (Download, unzip, copy iot_telemetry_data.csv"
  echo "  to data/raw/), or create a Kaggle API token and re-run with KAGGLE_USERNAME=... KAGGLE_KEY=..."
fi
if ls data/raw/beijing/PRSA_Data_*_20130301-20170228.csv >/dev/null 2>&1; then
  CORPORA="$CORPORA beijing"; echo "beijing: $(ls data/raw/beijing/PRSA_Data_*.csv | wc -l) files (12 expected)"
else
  echo "SKIPPING beijing: no PRSA_Data_*.csv files in data/raw/beijing/"
fi
[ -n "$CORPORA" ] || { echo "no corpus available; nothing to run"; exit 1; }

step "Unit tests"
python -m pytest -q 2>&1 | tee logs/pytest.log | tail -2

cd bench
step "Corpus statistics (must match data/README.md)"
python corpus_stats.py 2>&1 | tee ../logs/corpus_stats.log
python - <<'PY'
import json
s = json.load(open("../results/corpus_stats.json"))
# N, N_d and the posting total hold for any band rule, so they alone cannot catch a
# band-edge difference; the maximum posting length and largest single-tag sum can.
# Values are those of the C++ corpus builder, as the manuscript states them.
want = {"telemetry": {"N": 11580, "Nd": 405184, "postings": 3646656, "max": 404702,
                      "largest_sum": 908575470},
        "beijing": {"N": 35162, "Nd": 420370, "postings": 4624070, "max": 102344,
                    "largest_sum": 698963226}}
for k, w in want.items():
    if k not in s:
        print(k, "not available"); continue
    bad = {f: (s[k][f], v) for f, v in w.items() if s[k][f] != v}
    print(k, "OK" if not bad else f"MISMATCH (got, C++ builder): {bad}")
PY

step "Per-tag posting lengths (for re-analysing leakage without the raw data)"
python dump_lengths.py 2>&1 | tee ../logs/dump_lengths.log

for c in $CORPORA; do
  step "Correctness on $c"
  python correctness.py --corpus "$c" --nd 20000 --tags 200 2>&1 | tee "../logs/correctness_$c.log"
  step "Leakage attack on $c: unmasked, power-of-two padded, volume-hiding, masked"
  python bench_leakage.py --corpus "$c" 2>&1 | tee "../logs/leakage_$c.log"
  step "Range aggregation on $c"
  if [ "$c" = telemetry ]; then
    python bench_range_real.py --corpus telemetry 2>&1 | tee ../logs/range_real_telemetry.log
  else
    python bench_range_real.py --corpus beijing --time day 2>&1 | tee ../logs/range_real_beijing_day.log
    if [ "${FULL:-0}" = 1 ]; then
      python bench_range_real.py --corpus beijing --time hour --reps 3 --trials 10 2>&1 | tee ../logs/range_real_beijing_hour.log
    fi
  fi
done
cd ..

step "Pack results"
out="crshe_server_results_$(hostname)_$(date +%Y%m%d_%H%M).tar.gz"
tar czf "$out" results logs
echo "Send back: $out"
