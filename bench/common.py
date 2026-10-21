"""Shared helpers: timing with medians and IQR, environment stamp, synthetic
fast-path deployments whose cost depends only on (N, templates)."""
import json
import os
import platform
import statistics
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crshe import Owner, Provider, he  # noqa: E402


def timed(fn, reps):
    ts, out = [], None
    for _ in range(reps):
        t0 = time.perf_counter()
        out = fn()
        ts.append(time.perf_counter() - t0)
    q = statistics.quantiles(ts, n=4) if len(ts) >= 2 else [ts[0]] * 3
    return {"median_ms": 1e3 * statistics.median(ts), "q1_ms": 1e3 * q[0],
            "q3_ms": 1e3 * q[2], "reps": reps}, out


def environment():
    cpu = "unknown"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    import openfhe
    return {"cpu": cpu, "cores": os.cpu_count(), "python": platform.python_version(),
            "openfhe_python": getattr(openfhe, "__version__", "1.5.1"),
            "omp_threads": os.environ.get("OMP_NUM_THREADS", "default"),
            "implementation": "crshe reference (Python driver, OpenFHE C++ kernels)"}


def tag_domain_deployment(N, Nd=4096, n=2, bfv=None, seed=0, templates=("sum",)):
    """A deployment with exactly N tags. Fast-path cost depends on N and the
    number of templates only, so random sparse postings suffice."""
    rng = np.random.default_rng(seed)
    values = rng.integers(1900, 3100, Nd)
    postings = [rng.choice(Nd, size=int(rng.integers(0, 8)), replace=False) for _ in range(N)]
    tags = [f"tag{i:07d}" for i in range(N)]
    pool = {"count": np.ones(Nd, dtype=np.int64), "sum": values,
            "weighted": ((np.arange(Nd) % 5) + 1) * values, "sumsq": (values // 10) ** 2}
    tm = {k: pool[k] for k in templates}
    o = Owner(tags, postings, values, tm, n=n, bfv=bfv, seed=seed)
    return o, tags, postings, values


def save(name, payload):
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "results"), exist_ok=True)
    path = os.path.join(os.path.dirname(__file__), "..", "results", name)
    payload = {"environment": environment(), **payload}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print("wrote", os.path.relpath(path))
