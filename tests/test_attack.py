import numpy as np

from crshe import attack


def test_unmasked_unique_lengths_fully_reidentified_masked_not():
    lengths = np.array([5, 9, 13, 40, 40, 40, 77])
    classes = ["a", "a", "a", "b", "b", "b", "a"]
    r = attack.run(lengths, classes, "unmasked")
    assert r["per_class"]["a"] == 1.0
    assert abs(r["per_class"]["b"] - 1 / 3) < 1e-12
    m = attack.run(lengths, classes, "masked", key=bytes(16), n_records=100)
    assert m["overall"] <= 1 / 7 + 1e-12      # at most one lucky row
    v = attack.run(lengths, classes, "volume_hiding")
    assert abs(v["overall"] - 1 / 7) < 1e-12


def test_padding_merges_lengths():
    assert list(attack.pad_pow([1, 2, 3, 5, 8, 9], 2)) == [1, 2, 4, 8, 8, 16]
