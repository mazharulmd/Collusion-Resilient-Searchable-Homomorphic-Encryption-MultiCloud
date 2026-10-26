"""Turn results/*.json into the LaTeX tables the revised manuscript \\inputs,
so no number is transcribed by hand."""
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUTS = [os.path.join(ROOT, "paper", d, "tables") for d in ("revision", "iot-elsevier")]


def write(name, rows):
    for out in OUTS:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, name), "w") as f:
            f.write("\n".join(rows) + "\n")


def load(name):
    with open(os.path.join(ROOT, "results", name)) as f:
        return json.load(f)


def ms(t):
    return f"${t['median_ms']:.1f}$"


def num(x):
    return f"${x:,}$".replace(",", "{,}")


# ---- packing and single-server ------------------------------------------
d = load("response_and_single_server.json")
lines = []
labels = [("submitted_2ct_1tpl", "Two ct (unpacked)", 1),
          ("packed_1ct_1tpl", "Packed, 1 ct", 1),
          ("packed_1ct_1tpl_compressed", "Packed + compressed", 1),
          ("submitted_2ct_x4_4tpl", "$4\\times$ two ct", 4),
          ("packed_1ct_4tpl", "Packed, 1 ct", 4),
          ("packed_1ct_4tpl_compressed", "Packed + compressed", 4)]
for r in d["rows"]:
    lines.append(f"\\multicolumn{{4}}{{@{{}}l}}{{\\emph{{$N={r['N']:,}$ tags}}}} \\\\".replace(",", "{,}"))
    for key, lab, k in labels:
        c = r["configs"][key]
        lines.append(f"{lab} & ${k}$ & {ms(c['provider'])} & {num(c['downlink_bytes_per_provider'])} \\\\")
    s = r["single_server"]
    lines.append(f"Single server (vi) & $1$ & {ms(s['server'])} & {num(s['downlink_bytes'])} \\\\")
    lines.append("\\midrule")
lines[-1] = "\\bottomrule"
write("packing.tex", lines)

up = []
for r in d["rows"]:
    s = r["single_server"]
    up.append(f"$N={r['N']:,}$ & {num(r['dpf_key_bytes'])} & {num(s['uplink_bytes'])} & "
              f"${s['query_ciphertexts']}$ & {ms(s['client_query_encrypt'])} \\\\".replace(",", "{,}", 1))
write("uplink.tex", up)

# ---- flexible path --------------------------------------------------------
d = load("flexible_path.json")
rows = sorted(d["rows"], key=lambda r: r["Nd"])
fl = []
for r in rows:
    fl.append(f"{num(r['Nd'])} & {ms(r['retrieve'])} & {ms(r['contract'])} & "
              f"{num(r['round2_uplink_bytes'][-1])} & {num(r['round2_downlink_bytes_compressed'])} & "
              f"${r['masked_index_bytes'] / 1e9:.2f}$ \\\\")
write("flexible.tex", fl)

# ---- MAC detection ----------------------------------------------------------
d = load("mac_detection.json")
names = {"inconsistent": "Constant on value row", "dense": "$e_j+d$, $d$ uniform",
         "scale": "$k\\,e_j$", "single_row": "$e_j+c\\,u_x$, random $x$"}
mac = []
for kind, lab in names.items():
    g, r = d["results"]["global"][kind], d["results"]["row"][kind]
    cell = lambda c: f"${c['detected']}$ / ${c['undetected_wrong']}$ / ${c['undetected_correct']}$"
    mac.append(f"{lab} & {cell(g)} & {cell(r)} \\\\")
write("mac.tex", mac)
print("wrote tables to", [os.path.relpath(o, ROOT) for o in OUTS])


# ---- v3: range aggregation and packed index -------------------------------
V3 = os.path.join(ROOT, "paper", "v3", "tables")
os.makedirs(V3, exist_ok=True)


def write_v3(name, rows):
    with open(os.path.join(V3, name), "w") as f:
        f.write("\n".join(rows) + "\n")


d = load("range_aggregation.json")
rg = []
pc, cb = d["modes"]["per_corner"]["by_window"], d["modes"]["combined"]["by_window"]
for a, b in zip(pc, cb):
    assert a["window_minutes"] == b["window_minutes"]
    rg.append(f"{num(a['window_minutes'])} & {ms(a['dpf_eval_all_corners'])} & {ms(a['provider_total'])} & "
              f"{ms(b['dpf_eval_all_corners'])} & {ms(b['provider_total'])} \\\\")
write_v3("range.tex", rg)
sc = [f"{num(s['M'])} & ${s['chunks']}$ & {ms(s['dpf_eval_all_corners'])} & {ms(s['provider_total'])} \\\\"
      for s in d["cube_scaling"]]
write_v3("range_scaling.tex", sc)

d = load("packed_index.json")
pk = []
for r in d["rows"]:
    label = "unpacked" if r["pack_bits"] == 1 else f"{r['pack_bits']} bits/word"
    pk.append(f"{num(r['Nd'])} & {label} & ${r['index_bytes'] / 1e9:.3f}$ & {ms(r['retrieve'])} & "
              f"{num(r['retrieve_downlink_bytes'])} \\\\")
write_v3("packed.tex", pk)
for name in ("packing.tex", "uplink.tex", "flexible.tex", "mac.tex"):
    with open(os.path.join(OUTS[0], name)) as src_f, open(os.path.join(V3, name), "w") as dst:
        dst.write(src_f.read())
print("wrote v3 tables to", os.path.relpath(V3, ROOT))

# ---- v4: verified range layout, verification modes, role-scoped access ------
V4 = os.path.join(ROOT, "paper", "v4", "tables")
os.makedirs(V4, exist_ok=True)


def write_v4(name, rows):
    with open(os.path.join(V4, name), "w") as f:
        f.write("\n".join(rows) + "\n")


for name in ("range_scaling.tex", "packed.tex", "packing.tex", "uplink.tex", "flexible.tex"):
    with open(os.path.join(V3, name)) as src_f, open(os.path.join(V4, name), "w") as dst:
        dst.write(src_f.read())

d = load("range_aggregation.json")
ds_ = load("range_session.json")
pc, cb = d["modes"]["per_corner"]["by_window"], d["modes"]["combined"]["by_window"]
se = ds_["modes"]["session"]["by_window"]
rg = []
for a, b, c in zip(pc, cb, se):
    assert a["window_minutes"] == b["window_minutes"] == c["window_minutes"]
    rg.append(f"{num(a['window_minutes'])} & {ms(a['provider_total'])} & {ms(b['provider_total'])} & "
              f"{ms(c['dpf_eval_all_corners'])} & {ms(c['provider_total'])} \\\\")
write_v4("range.tex", rg)

v = load("verification_modes.json")["results"]
KIND = [("inconsistent", "Constant on value slot"), ("dense", "Share $+\\,d$, $d$ uniform"),
        ("scale", "$k\\cdot$share"), ("random_point", "Share $+\\,c\\,u_x$, random $x$"),
        ("hidden_point", "Share $+\\,c\\,u_x$, $x$ = queried point")]


def dw(c):
    return f"${c['detected']}/{c['undetected_wrong']}$"


ROWS = [("fast", "global", "Fast", "one key"), ("fast", "row", "", "per-row keys"),
        ("fast", "session", "", "session"), ("range", "combined", "Range", "one key"),
        ("range", "per_corner", "", "per-cell keys"), ("range", "session", "", "session"),
        ("flexible", "global", "Flexible", "one key"), ("flexible", "session", "", "session"),
        ("retrieval", "width_only", "Retrieval", "width check"), ("retrieval", "session", "", "session")]
vt = []
for path, mode, plab, mlab in ROWS:
    cells = " & ".join(dw(v[path][mode][k]) for k, _ in KIND)
    if path != "fast" and plab:
        vt.append("\\midrule")
    vt.append(f"{plab} & {mlab} & {cells} \\\\")
write_v4("verify.tex", vt)

ra = load("role_access.json")["results"]
sk, rs = ra["single_key"], ra["role_scoped"]
write_v4("roles.tex", [
    f"One mask key & {num(sk['rows_recovered_exactly'])} & {num(sk['other_role_postings_recovered'])} of "
    f"{num(sk['other_role_postings'])} & n/a \\\\",
    f"Role-scoped keys & {num(rs['rows_recovered_exactly'])} & {num(rs['other_role_postings_recovered'])} of "
    f"{num(rs['other_role_postings'])} & ${100 * rs['other_role_words_passing_width_check'] / rs['other_role_words']:.2f}\\%$ \\\\"])
print("wrote v4 tables to", os.path.relpath(V4, ROOT))

# ---- v5: real-corpus range aggregation and leakage baselines ---------------
V5 = os.path.join(ROOT, "paper", "v5", "tables")
os.makedirs(V5, exist_ok=True)


def write_v5(name, rows):
    with open(os.path.join(V5, name), "w") as f:
        f.write("\n".join(rows) + "\n")


for name in os.listdir(V4):
    with open(os.path.join(V4, name)) as src_f, open(os.path.join(V5, name), "w") as dst:
        dst.write(src_f.read())

rr = []
for fname, label in (("range_real_telemetry.json", "Primary corpus, device $\\times$ minute $\\times$ CO band"),
                     ("range_real_beijing_day.json", "Second corpus, site $\\times$ day $\\times$ PM$_{2.5}$ band")):
    d = load(fname)
    cb, se = d["modes"]["combined"], d["modes"]["session"]
    dims = "\\times".join(f"{x:,}".replace(",", "{,}") for x in d["dims"])
    if rr:
        rr.append("\\midrule")
    rr.append(f"\\multicolumn{{4}}{{@{{}}l}}{{\\emph{{{label}: ${dims}$, $M={num(cb['M'])[1:-1]}$}}}} \\\\")
    unit = "min" if d["window_unit"] == "minutes" else "d"
    for a, b in zip(cb["by_window"], se["by_window"]):
        assert a["window"] == b["window"] and a["result"] == b["result"]
        rr.append(f"{num(a['window'])}\\,{unit} & {ms(a['provider_total'])} & "
                  f"{ms(b['dpf_eval_all_keys'])} & {ms(b['provider_total'])} \\\\")
write_v5("range_real.tex", rr)

CLASS = {"device": "Device", "light": "Light flag", "motion": "Motion flag", "co": "CO band",
         "humidity": "Humidity band", "lpg": "LPG band", "smoke": "Smoke band",
         "temp": "Temperature band", "minute": "One-minute window", "site": "Site",
         "wd": "Wind direction", "hour": "Hour", "CO": "CO band", "NO2": "NO$_2$ band",
         "O3": "O$_3$ band", "PM10": "PM$_{10}$ band", "PM2.5": "PM$_{2.5}$ band",
         "SO2": "SO$_2$ band", "PRES": "Pressure band", "DEWP": "Dew-point band"}
ORDER = {"telemetry": ["device", "light", "motion", "co", "lpg", "smoke", "humidity", "temp", "minute"],
         "beijing": ["site", "wd", "PM2.5", "PM10", "SO2", "NO2", "CO", "O3", "PRES", "DEWP", "hour"]}
SCHEMES = ("unmasked", "padded", "volume_hiding", "masked")


def pct(x, nd=1):
    return f"${100 * x:.{nd}f}\\%$"


lk = []
for corpus, label in (("telemetry", "Primary corpus"), ("beijing", "Second corpus")):
    runs = {r["scheme"]: r for r in load(f"leakage_{corpus}.json")["runs"] if r["fraction"] == 1.0}
    if lk:
        lk.append("\\midrule")
    lk.append(f"\\multicolumn{{5}}{{@{{}}l}}{{\\emph{{{label}}}}} \\\\")
    for c in ORDER[corpus]:
        lk.append(f"{CLASS[c]} & " + " & ".join(pct(runs[s]["per_class"][c]) for s in SCHEMES) + " \\\\")
    lk.append("All tags & " + " & ".join(pct(runs[s]["overall"], 3) for s in SCHEMES) + " \\\\")
    lk.append(f"Random guessing & \\multicolumn{{4}}{{c}}{{{pct(runs['unmasked']['random_guess'], 4)}}} \\\\")
write_v5("leakage_real.tex", lk)
print("wrote v5 tables to", os.path.relpath(V5, ROOT))
