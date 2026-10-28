"""Checks reed_solomon.py against the erasure code of JAM, as polkajam does it.

erasure_shards follows the erasure_shards function of polkajam, which calls
reed-solomon-simd 3.0.1. The files in vectors/ are polkajam dumps of that
function: vectors/full has 1023 shards, and vectors/tiny has 6 shards.

Run it with `python3 test_jam.py`.
"""
import functools
import json
import time
from pathlib import Path

import reed_solomon

HERE = Path(__file__).resolve().parent
VECTORS = {"tiny": 6, "full": 1023}

SEGMENT_LEN = 4104
POINT_LEN = 2
VALS_PER_CORE = 3
MIN_VAL_COUNT = 2 * VALS_PER_CORE
POINTS_PER_BLOCK = 32


def recovery_threshold(shard_count):
    threshold = shard_count // VALS_PER_CORE + 1
    while SEGMENT_LEN % (POINT_LEN * threshold) != 0:
        threshold -= 1
    return threshold


def to_crate_shard(piece, chunks):
    piece = piece.ljust(chunks * POINT_LEN, b"\0")
    points = [piece[index] | piece[index + 1] << 8
              for index in range(0, len(piece), POINT_LEN)]
    points += [0] * (-len(points) % POINTS_PER_BLOCK)
    return reed_solomon.symbols_to_shard(points)


def from_crate_shard(shard, chunks):
    points = reed_solomon.shard_to_symbols(shard)[:chunks]
    return b"".join(point.to_bytes(POINT_LEN, "little") for point in points)


def erasure_shards(data, shard_count):
    if shard_count < MIN_VAL_COUNT:
        raise ValueError("shard count below the minimum")
    threshold = recovery_threshold(shard_count)
    chunks = -(-len(data) // (threshold * POINT_LEN))
    piece_len = chunks * POINT_LEN
    pieces = [data[start:start + piece_len]
              for start in range(0, len(data), piece_len)]
    pieces += [b""] * (threshold - len(pieces))

    original = [to_crate_shard(piece, chunks) for piece in pieces]
    recovery_count = shard_count - threshold
    recovery = reed_solomon.encode(threshold, recovery_count, original)
    return ([piece.ljust(piece_len, b"\0") for piece in pieces]
            + [from_crate_shard(shard, chunks) for shard in recovery])


def keep_coefficients():
    # The full vectors have the same points, so the Lagrange coefficients
    # (about a minute for each vector) are the same for all of them.
    compute = reed_solomon.lagrange_coefficients

    @functools.cache
    def cached(points, target):
        return compute(points, target)

    reed_solomon.lagrange_coefficients = (
        lambda points, target: cached(tuple(points), target))


def check_thresholds():
    # The values that polkajam asserts, and its definition of D(v): the
    # largest d <= v/3 + 1 such that a segment splits into pieces of d points.
    thresholds = [recovery_threshold(count) for count in (6, 78, 1023)]
    assert thresholds == [3, 27, 342]
    for count in range(MIN_VAL_COUNT, 1024, VALS_PER_CORE):
        largest = max(threshold
                      for threshold in range(1, count // VALS_PER_CORE + 2)
                      if SEGMENT_LEN % (POINT_LEN * threshold) == 0)
        assert recovery_threshold(count) == largest, f"D({count})"


def check_vector(path, shard_count):
    vector = json.loads(path.read_text())
    data = bytes.fromhex(vector["data"].removeprefix("0x"))
    expected = [bytes.fromhex(shard.removeprefix("0x"))
                for shard in vector["shards"]]
    assert erasure_shards(data, shard_count) == expected, \
        f"{path.parent.name}/{path.name}: shards differ"


def run():
    check_thresholds()
    print("thresholds ok", flush=True)
    keep_coefficients()
    for spec, shard_count in VECTORS.items():
        paths = sorted((HERE / "vectors" / spec).glob("ec-*.json"))
        assert len(paths) == 6, f"{spec}: expected 6 vectors"
        for path in paths:
            print(f"{spec}/{path.name} ...", end=" ", flush=True)
            start = time.monotonic()
            check_vector(path, shard_count)
            print(f"ok ({time.monotonic() - start:.1f} s)", flush=True)


if __name__ == "__main__":
    run()
    print("12 vectors pass")
