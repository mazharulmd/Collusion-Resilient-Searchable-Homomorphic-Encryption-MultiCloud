#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Emulated wide-area links for E3, for use ONLY when real cloud instances are
# not available.
#
# If you use this, the paper must say so explicitly: "inter-region round-trip
# times were measured between <regions> on <date> and reproduced locally with
# tc netem". Reviewers accept documented emulation. They do not accept
# emulation presented as a real deployment.
#
#   sudo bench/netem_wan.sh add 40 5      # 40 ms RTT, 5 ms jitter
#   sudo bench/netem_wan.sh del
#
# Measure the real RTTs first, e.g. from an instance in each region:
#   ping -c 100 <other-region-endpoint>
# and use those numbers here rather than plausible-looking ones.
set -euo pipefail

DEV="${DEV:-lo}"
CMD="${1:-show}"
RTT_MS="${2:-40}"
JITTER_MS="${3:-5}"

case "$CMD" in
  add)
    HALF=$(awk "BEGIN{printf \"%.1f\", $RTT_MS/2}")
    HJIT=$(awk "BEGIN{printf \"%.1f\", $JITTER_MS/2}")
    tc qdisc replace dev "$DEV" root netem delay "${HALF}ms" "${HJIT}ms" distribution normal
    echo "applied ${RTT_MS}ms RTT (+-${JITTER_MS}ms) on $DEV"
    echo "verify with: ping -c 20 127.0.0.1"
    echo
    echo "REMEMBER: record in the paper that this is emulated, and where the"
    echo "RTT figure came from."
    ;;
  del)
    tc qdisc del dev "$DEV" root 2>/dev/null || true
    echo "removed netem from $DEV"
    ;;
  show)
    tc qdisc show dev "$DEV"
    ;;
  *)
    echo "usage: $0 {add <rtt_ms> <jitter_ms>|del|show}" >&2
    exit 1
    ;;
esac
