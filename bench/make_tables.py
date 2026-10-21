"""Turn results/*.json into the LaTeX tables the revised manuscript \\inputs,
so no number is transcribed by hand."""
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "paper", "revision", "tables")
os.makedirs(OUT, exist_ok=True)


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
labels = [("submitted_2ct_1tpl", "Submitted, 2 ct", 1),
          ("packed_1ct_1tpl", "Packed, 1 ct", 1),
          ("packed_1ct_1tpl_compressed", "Packed + compressed", 1),
          ("submitted_2ct_x4_4tpl", "Submitted, $4\\times$2 ct", 4),
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
with open(os.path.join(OUT, "packing.tex"), "w") as f:
    f.write("\n".join(lines) + "\n")

up = []
for r in d["rows"]:
    s = r["single_server"]
    up.append(f"$N={r['N']:,}$ & {num(r['dpf_key_bytes'])} & {num(s['uplink_bytes'])} & "
              f"${s['query_ciphertexts']}$ & {ms(s['client_query_encrypt'])} \\\\".replace(",", "{,}", 1))
with open(os.path.join(OUT, "uplink.tex"), "w") as f:
    f.write("\n".join(up) + "\n")

# ---- flexible path --------------------------------------------------------
d = load("flexible_path.json")
rows = sorted(d["rows"], key=lambda r: r["Nd"])
fl = []
for r in rows:
    fl.append(f"{num(r['Nd'])} & {ms(r['retrieve'])} & {ms(r['contract'])} & "
              f"{num(r['round2_uplink_bytes'][-1])} & {num(r['round2_downlink_bytes_compressed'])} & "
              f"${r['masked_index_bytes'] / 1e9:.2f}$ \\\\")
with open(os.path.join(OUT, "flexible.tex"), "w") as f:
    f.write("\n".join(fl) + "\n")

# ---- MAC detection ----------------------------------------------------------
d = load("mac_detection.json")
names = {"inconsistent": "Constant on value row", "dense": "$e_j+d$, $d$ uniform",
         "scale": "$k\\,e_j$", "single_row": "$e_j+c\\,u_x$, random $x$"}
mac = []
for kind, lab in names.items():
    g, r = d["results"]["global"][kind], d["results"]["row"][kind]
    cell = lambda c: f"${c['detected']}$ / ${c['undetected_wrong']}$ / ${c['undetected_correct']}$"
    mac.append(f"{lab} & {cell(g)} & {cell(r)} \\\\")
with open(os.path.join(OUT, "mac.tex"), "w") as f:
    f.write("\n".join(mac) + "\n")
print("wrote", sorted(os.listdir(OUT)))
