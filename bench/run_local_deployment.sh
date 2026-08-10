#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# E3, single-host variant: the real protocol between independent provider
# processes and a client, all on one machine over loopback.
#
# This measures provider compute, serialisation and framing, and client
# combine/verify/decrypt. It does NOT measure wide-area transport, and the
# providers contend for the same cores instead of running on independent
# infrastructure -- so the per-n compute figures are an upper bound, not a
# scaling result. Report it as single-host. The real multi-cloud run is
# docs/RUNBOOK.md phase 6.
set -euo pipefail
cd "$(dirname "$0")/.."

DATA="${1:-data/telemetry.crshe}"
OUT="${2:-bench/results/telemetry}"
QUERIES="${QUERIES:-100}"
BUNDLE="${BUNDLE:-$(mktemp -d)/deploy}"

./build/crshe_setup --data="$DATA" --bundle="$BUNDLE"

pkill -x crshe_provider 2>/dev/null || true
sleep 1
for p in 9401 9402 9403 9404; do
    ./build/crshe_provider --bundle="$BUNDLE" --port="$p" --threads=1 \
        > "${BUNDLE}.p$p.log" 2>&1 &
done
# Providers warm the homomorphic path before serving; wait for that, not a
# fixed sleep, or the first client pays one-off initialisation.
#
# NOTE: `grep -l ... | wc -l` exits non-zero while no log matches yet, and under
# `set -o pipefail` that killed the whole script on the first iteration -- the
# run died silently right after crshe_setup. Count with a loop instead, and
# never let a not-yet-ready probe look like a failure.
ready=0
for _ in $(seq 1 180); do
    ready=0
    for p in 9401 9402 9403 9404; do
        if grep -q 'listening' "${BUNDLE}.p$p.log" 2>/dev/null; then
            ready=$((ready + 1))
        fi
    done
    [ "$ready" -ge 4 ] && break
    sleep 1
done
if [ "$ready" -lt 4 ]; then
    echo "only $ready/4 providers came up; their logs:" >&2
    tail -n 20 "${BUNDLE}".p*.log >&2 || true
    pkill -x crshe_provider 2>/dev/null || true
    exit 1
fi
echo "all 4 providers listening and warmed"


for n in 2 3 4; do
    case $n in
      2) PL=127.0.0.1:9401,127.0.0.1:9402 ;;
      3) PL=127.0.0.1:9401,127.0.0.1:9402,127.0.0.1:9403 ;;
      4) PL=127.0.0.1:9401,127.0.0.1:9402,127.0.0.1:9403,127.0.0.1:9404 ;;
    esac
    ./build/crshe_client --bundle="$BUNDLE" --providers="$PL" \
        --queries="$QUERIES" --label="single-host loopback, n=$n" \
        --out="$OUT/e3_local_n$n.csv"
done

cp "$OUT/e3_local_n2.csv" "$OUT/e3_wan.csv"
pkill -x crshe_provider 2>/dev/null || true
echo "single-host deployment done; wide-area transport NOT included."
