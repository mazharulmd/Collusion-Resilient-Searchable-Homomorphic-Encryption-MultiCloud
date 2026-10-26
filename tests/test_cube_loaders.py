"""The real-corpus cube loaders, on small files with the published columns."""
import csv
import os

import numpy as np

from crshe import corpus


def write_telemetry(path, rng, n=500):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "device", "co", "humidity", "light", "lpg", "motion", "smoke", "temp"])
        for i in range(n):
            w.writerow([1594512094.39 + 37 * i, f"dev{rng.integers(0, 3)}", rng.random() / 100,
                        50 + rng.random(), "false", rng.random() / 100, "false", rng.random() / 50,
                        19 + 10 * rng.random()])


def write_beijing(directory, rng, sites=("A", "B"), days=5):
    os.makedirs(directory)
    for s in sites:
        with open(os.path.join(directory, f"PRSA_Data_{s}_20130301-20170228.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["No", "year", "month", "day", "hour", "PM2.5", "PM10", "SO2", "NO2", "CO", "O3",
                        "TEMP", "PRES", "DEWP", "RAIN", "wd", "WSPM", "station"])
            k = 0
            for d in range(1, days + 1):
                for h in range(24):
                    pm = "NA" if rng.random() < 0.05 else f"{rng.random() * 300:.1f}"
                    temp = "NA" if rng.random() < 0.02 else f"{rng.random() * 30 - 5:.1f}"
                    k += 1
                    w.writerow([k, 2013, 3, d, h, pm, 1, 1, 1, 1, 1, temp, 1010, -5, 0, "N", 1, s])


def test_telemetry_cube(tmp_path):
    rng = np.random.default_rng(1)
    p = tmp_path / "t.csv"
    write_telemetry(p, rng)
    c = corpus.cube_telemetry(str(p))
    assert c.dims[0] == len(set(c.labels[0])) <= 3 and c.dims[2] == 10
    assert c.cells.shape == (500, 3) and (c.cells < np.array(c.dims)).all()
    assert c.truth(tuple((0, s - 1) for s in c.dims), c.values) == int(c.values.sum())
    # minute index is dense and ordered
    assert c.cells[:, 1].min() == 0 and len(np.unique(c.cells[:, 1])) == c.dims[1]


def test_beijing_cube_day_and_hour(tmp_path):
    rng = np.random.default_rng(2)
    d = tmp_path / "bj"
    write_beijing(str(d), rng)
    day = corpus.cube_beijing(str(d), time="day")
    hour = corpus.cube_beijing(str(d), time="hour")
    assert day.dims == (2, 5, 11) and hour.dims[1] == 5 * 24
    assert len(day.values) == len(hour.values)                  # same records
    assert (day.cells[:, 2] == 10).any()                        # missing PM2.5 has its own band
    assert day.truth(((0, 1), (0, 4), (0, 10)), day.values) == int(day.values.sum())
