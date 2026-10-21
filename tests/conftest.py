import numpy as np
import pytest

from crshe import he


@pytest.fixture(scope="session")
def bfv():
    return he.BFV()


@pytest.fixture(scope="session")
def small_db():
    rng = np.random.default_rng(1)
    Nd, ntags = 2500, 300
    values = rng.integers(1000, 4000, Nd)
    postings = [np.sort(rng.choice(Nd, size=int(min(Nd, rng.zipf(1.5))), replace=False))
                for _ in range(ntags - 2)]
    postings.append(np.array([], dtype=np.int64))       # empty posting list
    postings.append(np.arange(Nd - 1))                   # matches all but one record
    tags = [f"t{i:03d}" for i in range(ntags)]
    w = (np.arange(Nd) % 5) + 1
    templates = {"count": np.ones(Nd, dtype=np.int64), "sum": values,
                 "weighted": w * values, "sumsq": (values // 100) ** 2}
    return dict(tags=tags, postings=postings, values=values, w=w, templates=templates)
