"""Write NUMBERS.md: every number the focused manuscript may quote, read from
results/*.json, with the file and field it came from.

    python paper/focused/make_numbers.py

Authors copy numbers from NUMBERS.md, not from older drafts. Times are medians;
"a-b" is the smallest and largest median over the listed queries. Nothing here
is rounded toward a claim: values are printed as stored, then to the stated
number of decimals.
"""
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "NUMBERS.md")


def load(name):
    with open(os.path.join(ROOT, "results", name)) as f:
        return json.load(f)


def med(t):
    return t["median_ms"]


def span(vals, scale=1.0, nd=1):
    lo, hi = min(vals) * scale, max(vals) * scale
    return f"{lo:,.{nd}f}" if f"{lo:,.{nd}f}" == f"{hi:,.{nd}f}" else f"{lo:,.{nd}f}–{hi:,.{nd}f}"


rows = []


def add(section, what, value, source):
    rows.append((section, what, value, source))


# ---- datasets and real cubes ------------------------------------------------------
for fname, label in (("range_real_telemetry.json", "Telemetry"), ("range_real_beijing_day.json", "Beijing")):
    d = load(fname)
    env = d["environment"]
    S = f"Real cube, {label}"
    add(S, "machine", f"{env['cpu']}, {env['cores']} vCPUs, OMP threads {env['omp_threads']}", f"{fname}: environment")
    add(S, "records", f"{d['records']:,}", f"{fname}: records")
    add(S, "axes and sizes", " × ".join(f"{a} ({s:,})" for a, s in zip(d["axes"], d["dims"])), f"{fname}: axes, dims")
    cb, se = d["modes"]["combined"], d["modes"]["session"]
    add(S, "cells M", f"{cb['M']:,}", f"{fname}: modes.combined.M")
    add(S, "table ciphertexts", f"{cb['column_ciphertexts']:,}", f"{fname}: modes.combined.column_ciphertexts")
    add(S, "window lengths tested", ", ".join(f"{w['window']:,}" for w in se["by_window"]) + f" {d['window_unit']}",
        f"{fname}: modes.session.by_window[].window")
    for mode, name in (("session", "verified"), ("combined", "unverified")):
        bw = d["modes"][mode]["by_window"]
        add(S, f"{name}: provider time per query (ms)", span([med(w["provider_total"]) for w in bw]),
            f"{fname}: modes.{mode}.by_window[].provider_total")
        add(S, f"{name}: of which DPF evaluation (ms)", span([med(w["dpf_eval_all_keys"]) for w in bw]),
            f"{fname}: modes.{mode}.by_window[].dpf_eval_all_keys")
        add(S, f"{name}: keys per provider", f"{bw[0]['keys_per_provider']}", f"{fname}: modes.{mode}.by_window[0].keys_per_provider")
        add(S, f"{name}: upload per provider (B)", f"{bw[0]['uplink_bytes_per_provider']:,}",
            f"{fname}: modes.{mode}.by_window[0].uplink_bytes_per_provider")
        add(S, f"{name}: response per provider (B)", span([w["downlink_bytes"] for w in bw], nd=0),
            f"{fname}: modes.{mode}.by_window[].downlink_bytes")
        add(S, f"{name}: query generation at the analyst (ms)", span([med(w["token"]) for w in bw], nd=1),
            f"{fname}: modes.{mode}.by_window[].token")
        add(S, f"{name}: combine, check, decrypt at the analyst (ms)", span([med(w["user_finish"]) for w in bw], nd=2),
            f"{fname}: modes.{mode}.by_window[].user_finish")
        e = d["modes"][mode]["edge_box"]
        add(S, f"{name}: box at the cube's origin, provider time (ms)", f"{med(e['provider_total']):,.1f}",
            f"{fname}: modes.{mode}.edge_box.provider_total")
        t = d["modes"][mode]["tamper"]
        add(S, f"{name}: tampered queries detected / accepted wrong", 
            f"{sum(v['detected'] for v in t.values())} / {sum(v['undetected_wrong'] for v in t.values())} "
            f"of {sum(v['detected'] + v['undetected_wrong'] + v['undetected_correct'] for v in t.values())}",
            f"{fname}: modes.{mode}.tamper")
    add(S, "single-server query, computed (B)", f"{d['single_server_uplink_bytes_computed']:,}",
        f"{fname}: single_server_uplink_bytes_computed (computed, not measured)")

# ---- layouts and cube size, synthetic ----------------------------------------------
ra, rs = load("range_aggregation.json"), load("range_session.json")
S = "Synthetic cube (telemetry dimensions), layouts"
add(S, "machine", f"{ra['environment']['cpu']}, {ra['environment']['cores']} vCPUs", "range_aggregation.json: environment")
for src, fn, mode, name in ((ra, "range_aggregation.json", "per_corner", "per-cell check keys"),
                            (ra, "range_aggregation.json", "combined", "unverified"),
                            (rs, "range_session.json", "session", "verified (per-query check)")):
    bw = src["modes"][mode]["by_window"]
    add(S, f"{name}: provider time (s)", span([med(w["provider_total"]) for w in bw], 1e-3, 2),
        f"{fn}: modes.{mode}.by_window[].provider_total")
S = "Cube size (unverified, d = 2, synthetic)"
for r in ra["cube_scaling"]:
    add(S, f"M = {r['M']:,} cells: provider time (ms)", f"{med(r['provider_total']):,.1f}",
        "range_aggregation.json: cube_scaling[].provider_total")

# ---- baselines -----------------------------------------------------------------------
rb = load("range_baselines.json")
S = "Same query three ways (synthetic, telemetry dimensions)"
add(S, "machine", f"{rb['environment']['cpu']}, {rb['environment']['cores']} vCPUs", "range_baselines.json: environment")
wk = rb["workers"]
for r in rb["rows"]:
    L = r["window_minutes"]
    pc = r["percell"]
    add(S, f"L = {L:,} min ({r['box_cells']:,} cells): per-cell keys, provider (ms)",
        f"{med(pc['provider']):,.1f}" + ("" if pc["measured"] else " (computed)"),
        "range_baselines.json: rows[].percell.provider" + ("" if pc["measured"] else " (measured=false)"))
    add(S, f"L = {L:,} min: per-cell keys, upload per provider (B)", f"{pc['uplink_bytes_per_provider']:,}",
        "range_baselines.json: rows[].percell.uplink_bytes_per_provider")
for key, name in (("crshe_session_serial", "verified, 1 thread"), (f"crshe_session_pool{wk}", f"verified, {wk} workers"),
                  ("crshe_combined_serial", "unverified, 1 thread"), (f"crshe_combined_pool{wk}", f"unverified, {wk} workers")):
    add(S, f"CR-SHE {name}: provider (ms), all L", span([med(r[key]["provider"]) for r in rb["rows"]]),
        f"range_baselines.json: rows[].{key}.provider")
ss = [r for r in rb["rows"] if "single_server" in r]
add(S, "single server: server time (ms)", span([med(r["single_server"]["server"]) for r in ss]),
    "range_baselines.json: rows[].single_server.server")
add(S, "single server: query encryption at the client (ms)",
    span([med(r["single_server"]["client_query_encrypt"]) for r in ss]),
    "range_baselines.json: rows[].single_server.client_query_encrypt")
add(S, "single server: query ciphertexts", f"{ss[0]['single_server']['query_ciphertexts']}",
    "range_baselines.json: rows[].single_server.query_ciphertexts")
add(S, "single server: upload (B), measured", f"{ss[0]['single_server']['uplink_bytes']:,}",
    "range_baselines.json: rows[].single_server.uplink_bytes")
add(S, "per-key evaluation time used for computed points (ms)", f"{rb['per_key_eval_ms']:.1f}", "range_baselines.json: per_key_eval_ms")

# ---- tamper evidence, synthetic, range path ------------------------------------------
v = load("verification_modes.json")
S = f"Injected deviations, range path (synthetic cube {' × '.join(map(str, v['cube']))}, {v['trials']} trials each)"
for mode, name in (("combined", "no check (one stored key)"), ("per_corner", "per-cell stored keys"),
                   ("session", "per-query check")):
    for k, x in v["results"]["range"][mode].items():
        add(S, f"{name}, deviation '{k}': detected / accepted wrong / undetected but correct",
            f"{x['detected']} / {x['undetected_wrong']} / {x['undetected_correct']}",
            f"verification_modes.json: results.range.{mode}.{k}")

with open(OUT, "w") as f:
    f.write("# Numbers for the focused manuscript\n\n"
            "Generated by `make_numbers.py` from `results/*.json`. Do not edit by hand; re-run the script.\n"
            "Copy numbers from here, and keep the units. \"a–b\" is the smallest to largest median over the\n"
            "queries listed. \"(computed)\" marks a value that was not measured.\n")
    last = None
    for sec, what, val, src in rows:
        if sec != last:
            f.write(f"\n## {sec}\n\n| Quantity | Value | Source |\n|---|---|---|\n")
            last = sec
        f.write(f"| {what} | {val} | `{src}` |\n")
print("wrote", os.path.relpath(OUT), len(rows), "numbers")

# ---- table: injected deviations on the range path -------------------------------------
KINDS = (("inconsistent", "Constant"), ("dense", "Uniform"), ("scale", "Scale"),
         ("random_point", "Random point"), ("hidden_point", "Queried point"))
MODES = (("combined", "One stored key"), ("per_corner", "Per-cell stored keys"), ("session", "Per-query secret"))
os.makedirs(os.path.join(os.path.dirname(OUT), "tables"), exist_ok=True)
lines = []
for mode, name in MODES:
    cells = []
    for k, _ in KINDS:
        x = v["results"]["range"][mode][k]
        cells.append(f"{x['detected']} / {x['undetected_wrong']}")
    lines.append(f"{name} & " + " & ".join(cells) + r" \\")
real = []
for fname in ("range_real_telemetry.json", "range_real_beijing_day.json"):
    d = load(fname)
    for mode, name in (("combined", "One stored key"), ("session", "Per-query secret")):
        t = d["modes"][mode]["tamper"]
        real.append((fname, name, [f"{t[k]['detected']} / {t[k]['undetected_wrong']}" for k, _ in KINDS]))
with open(os.path.join(os.path.dirname(OUT), "tables", "tamper_range.tex"), "w") as f:
    f.write("% generated by make_numbers.py from results/verification_modes.json and results/range_real_*.json\n")
    f.write(r"\multicolumn{6}{@{}l}{\emph{Synthetic cube, %s cells, %d trials per deviation}} \\" %
            (r"$\times$".join(f"{s}" for s in v["cube"]), v["trials"]) + "\n")
    f.write("\n".join(lines) + "\n")
    for fname, label in (("range_real_telemetry.json", "Telemetry"), ("range_real_beijing_day.json", "Beijing")):
        n = sum(load(fname)["modes"]["session"]["tamper"]["dense"].values())
        f.write(r"\midrule" + "\n" + r"\multicolumn{6}{@{}l}{\emph{%s cube, %d trials per deviation}} \\" % (label, n) + "\n")
        for fn, name, cells in real:
            if fn == fname:
                f.write(f"{name} & " + " & ".join(cells) + r" \\" + "\n")
print("wrote tables/tamper_range.tex")
