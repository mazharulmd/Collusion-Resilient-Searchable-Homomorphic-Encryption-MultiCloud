"""Corpora: the two public IoT datasets of the manuscript, and a synthetic one.

Raw files are not redistributed. Download them into data/raw/ (see
data/README.md); the loaders rebuild the tag universe the manuscript
describes from the published files, with no hand curation.

telemetry  Environmental Sensor Telemetry (Stafford 2020), iot_telemetry_data.csv,
           405,184 MQTT messages from three devices. Tags: device id, one-minute
           window, decile band of co / humidity / lpg / smoke / temp, light and
           motion flags. Aggregated field: temperature in hundredths of a degree.
beijing    UCI Beijing Multi-Site Air-Quality (Zhang et al. 2017), twelve
           PRSA_Data_*.csv files, 420,768 hourly records. Tags: site, hour,
           wind direction, decile bands of six pollutants, pressure and dew
           point, with an explicit ':na' tag for a missing reading. Records
           with a missing temperature are dropped; temperature is shifted by
           +50 C and scaled to hundredths so it stays non-negative.
synthetic  Heavy-tailed postings with the same shape of tag classes, for tests
           and for latency measurements that depend only on (N, N_d). It is
           never used for a leakage or correctness figure about real data.
"""
import csv
import glob
import os
from collections import defaultdict

import numpy as np


class Corpus:
    def __init__(self, name, tags, postings, values, tag_class):
        order = np.argsort(np.array(tags, dtype=object), kind="stable")
        self.name = name
        self.tags = [tags[i] for i in order]          # rows in sorted tag order
        self.postings = [np.asarray(sorted(postings[i]), dtype=np.int64) for i in order]
        self.values = np.asarray(values, dtype=np.int64)
        self.tag_class = [tag_class[i] for i in order]

    @property
    def N(self):
        return len(self.tags)

    @property
    def Nd(self):
        return len(self.values)

    def lengths(self):
        return np.array([len(p) for p in self.postings], dtype=np.int64)

    def summary(self):
        L = self.lengths()
        return {"name": self.name, "N": self.N, "Nd": self.Nd,
                "postings": int(L.sum()), "median": float(np.median(L)),
                "mean": float(L.mean()), "max": int(L.max()),
                "largest_sum": int(max(self.values[p].sum() for p in self.postings))}

    def subsample(self, nd):
        """First `nd` records (in file order), keeping only tags that occur."""
        tags, posts, cls = [], [], []
        for t, p, c in zip(self.tags, self.postings, self.tag_class):
            q = p[p < nd]
            if len(q):
                tags.append(t); posts.append(q); cls.append(c)
        return Corpus(f"{self.name}[:{nd}]", tags, posts, self.values[:nd], cls)


def _band_tags(col, name, n_bands=10):
    x = np.array([np.nan if v in ("", "NA", None) else float(v) for v in col])
    ok = ~np.isnan(x)
    edges = np.quantile(x[ok], np.linspace(0.1, 0.9, 9))
    bands = np.digitize(x, edges)
    return [f"{name}:{b}" if good else f"{name}:na" for b, good in zip(bands, ok)]


def _build(name, record_tags, values, classes):
    posting = defaultdict(list)
    for i, tags in enumerate(record_tags):
        for t in tags:
            posting[t].append(i)
    tags = sorted(posting)
    return Corpus(name, tags, [posting[t] for t in tags], values,
                  [classes(t) for t in tags])


def load_telemetry(path="data/raw/iot_telemetry_data.csv"):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    bands = {c: _band_tags([r[c] for r in rows], c) for c in ("co", "humidity", "lpg", "smoke", "temp")}
    record_tags, values = [], []
    for i, r in enumerate(rows):
        t = [f"device:{r['device']}", f"minute:{int(float(r['ts'])) // 60}",
             f"light:{r['light']}", f"motion:{r['motion']}"]
        t += [bands[c][i] for c in bands]
        record_tags.append(t)
        values.append(int(round(float(r["temp"]) * 100)))
    return _build("telemetry", record_tags, values, lambda t: t.split(":")[0])


def load_beijing(directory="data/raw/beijing"):
    rows = []
    for fn in sorted(glob.glob(os.path.join(directory, "PRSA_Data_*.csv"))):
        with open(fn, newline="") as f:
            rows += [r for r in csv.DictReader(f) if r["TEMP"] not in ("", "NA")]
    if not rows:
        raise FileNotFoundError(f"no PRSA_Data_*.csv files in {directory}")
    cols = ("PM2.5", "PM10", "SO2", "NO2", "CO", "O3", "PRES", "DEWP")
    bands = {c: _band_tags([r[c] for r in rows], c) for c in cols}
    record_tags, values = [], []
    for i, r in enumerate(rows):
        hour = f"{int(r['year']):04d}{int(r['month']):02d}{int(r['day']):02d}{int(r['hour']):02d}"
        wd = r["wd"] if r["wd"] not in ("", "NA") else "na"
        t = [f"site:{r['station']}", f"hour:{hour}", f"wd:{wd}"] + [bands[c][i] for c in cols]
        record_tags.append(t)
        values.append(int(round((float(r["TEMP"]) + 50.0) * 100)))
    return _build("beijing", record_tags, values, lambda t: t.split(":")[0])


def synthetic(N=11_580, Nd=405_184, devices=3, seed=0):
    """Telemetry-shaped synthetic corpus: device tags, time windows of near
    equal length, ten bands per sensor channel, two boolean flags."""
    rng = np.random.default_rng(seed)
    windows = N - devices - 50 - 4
    record_tags = []
    dev = rng.integers(0, devices, Nd)
    win = np.sort(rng.integers(0, windows, Nd))
    chans = [rng.integers(0, 10, Nd) for _ in range(5)]
    light = rng.random(Nd) < 0.28
    motion = rng.random(Nd) < 0.001
    for i in range(Nd):
        t = [f"device:{dev[i]}", f"window:{win[i]:06d}",
             f"light:{bool(light[i])}", f"motion:{bool(motion[i])}"]
        t += [f"ch{c}:{chans[c][i]}" for c in range(5)]
        record_tags.append(t)
    values = rng.integers(1900, 3100, Nd)
    return _build("synthetic", record_tags, values, lambda t: t.split(":")[0])
