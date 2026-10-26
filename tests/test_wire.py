import socket

import numpy as np

from crshe import dpf, field, wire


def test_keys_round_trip_and_evaluate_identically():
    keys = list(dpf.gen(37, 1000, 2, beta=12345)) + dpf.gen(5, 300, 3) + dpf.share_vector(np.arange(50), 3)
    meta, blobs = wire.keys_to_wire(keys)
    back = wire.keys_from_wire(meta, blobs)
    for a, b in zip(keys, back):
        assert type(a) is type(b) and np.array_equal(a.eval_full(), b.eval_full())


def test_message_framing():
    a, b = socket.socketpair()
    wire.send_msg(a, {"op": "x", "n": 3}, [b"abc", bytes(100000)])
    h, blobs = wire.recv_msg(b)
    assert h == {"op": "x", "n": 3} and blobs[0] == b"abc" and len(blobs[1]) == 100000
