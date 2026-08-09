#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Phase 0: build dependencies on Ubuntu 22.04 / 24.04, then report what the
# machine can actually do.  Run this first and read the output -- in particular
# the AES line, because the DPF throughput numbers are only meaningful with
# hardware AES, and which instruction set you have must be stated in the paper.
set -euo pipefail

echo "== installing build dependencies =="
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake git pkg-config \
    libomp-dev \
    python3 python3-pip python3-venv \
    iproute2

echo
echo "== python packages =="
python3 -m pip install --user --upgrade matplotlib

echo
echo "== machine report =="
printf '  arch      : %s\n' "$(uname -m)"
printf '  cores     : %s\n' "$(nproc)"
printf '  memory    : %s\n' "$(free -h | awk '/^Mem:/{print $2}')"
printf '  cpu       : %s\n' "$(lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -1)"

echo
if grep -qw aes /proc/cpuinfo 2>/dev/null; then
    echo "  AES       : x86-64 AES-NI present"
    echo "              report the DPF numbers as measured with AES-NI."
elif grep -qw aes /proc/cpuinfo 2>/dev/null || \
     grep -qE 'Features.*\baes\b' /proc/cpuinfo 2>/dev/null; then
    echo "  AES       : ARMv8 crypto extensions present"
    echo "              report the DPF numbers as measured with ARMv8-CE."
else
    echo "  AES       : *** NO HARDWARE AES ***"
    echo "              The DPF will fall back to software AES. It stays correct,"
    echo "              but the throughput numbers are two orders of magnitude off"
    echo "              and must NOT be reported. On Oracle Cloud, VM.Standard.A1"
    echo "              (Ampere) has ARMv8 crypto and E4/E5 (AMD) have AES-NI;"
    echo "              check that your shape exposes them to the guest."
fi

echo
echo "Next: scripts/install_openfhe.sh"
