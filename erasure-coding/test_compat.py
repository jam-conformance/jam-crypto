"""Checks reed_solomon.py against the reed-solomon-simd crate (version 3.1.0).

For each case, both sides encode the same random shards and must give the
same recovery shards. Then each side decodes the recovery shards of the other
side from random sets of exactly original_count shards.

Run it with `python3 test_compat.py`; it needs cargo to build crate-cli.
"""
import random
import subprocess
from pathlib import Path

import reed_solomon

HERE = Path(__file__).resolve().parent
CLI = HERE / "crate-cli" / "target" / "release" / "crate-cli"

# (original_count, recovery_count, shard_bytes). The counts cover: low and
# high rate, the two tie cases (same power of two), more than one chunk on
# each side, one shard on each side. The sizes cover whole 64-byte blocks and
# a short last block.
CASES = [
    (3, 5, 64), (5, 3, 64), (4, 4, 64), (3, 4, 2), (7, 5, 6), (2, 2, 66),
    (1, 1, 2), (1, 6, 4), (6, 1, 4), (9, 7, 70), (7, 9, 128), (16, 3, 126),
    (3, 16, 66), (17, 17, 64), (33, 20, 2), (20, 33, 4), (100, 30, 4),
    (30, 100, 4),
]
DECODES_PER_CASE = 3


def crate(command, original_count, recovery_count, lines):
    output = subprocess.run(
        [CLI, command, str(original_count), str(recovery_count)],
        input="\n".join(lines), capture_output=True, text=True, check=True,
    ).stdout
    return output.split()


def crate_encode(original_count, recovery_count, original):
    lines = [shard.hex() for shard in original]
    words = crate("encode", original_count, recovery_count, lines)
    return [bytes.fromhex(shard) for shard in words]


def crate_decode(original_count, recovery_count, original, recovery):
    lines = [f"original {index} {shard.hex()}"
             for index, shard in original.items()]
    lines += [f"recovery {index} {shard.hex()}"
              for index, shard in recovery.items()]
    words = crate("decode", original_count, recovery_count, lines)
    pairs = zip(words[::2], words[1::2])
    return {int(index): bytes.fromhex(shard) for index, shard in pairs}


def check_case(original_count, recovery_count, shard_bytes, rng):
    original = [rng.randbytes(shard_bytes) for _ in range(original_count)]
    recovery = reed_solomon.encode(original_count, recovery_count, original)
    crate_recovery = crate_encode(original_count, recovery_count, original)
    assert recovery == crate_recovery, "recovery shards differ"

    for _ in range(DECODES_PER_CASE):
        total = original_count + recovery_count
        kept = rng.sample(range(total), original_count)
        given_original = {index: original[index]
                          for index in kept if index < original_count}
        given_indexes = [index - original_count
                         for index in kept if index >= original_count]
        expected = {index: original[index] for index in range(original_count)
                    if index not in given_original}

        restored = reed_solomon.decode(
            original_count, recovery_count, given_original,
            {index: crate_recovery[index] for index in given_indexes},
        )
        assert restored == expected, \
            "reed_solomon.py does not decode the crate shards"

        restored = crate_decode(
            original_count, recovery_count, given_original,
            {index: recovery[index] for index in given_indexes},
        )
        assert restored == expected, \
            "the crate does not decode the reed_solomon.py shards"


def run(seed=2026):
    manifest = HERE / "crate-cli" / "Cargo.toml"
    print("build crate-cli", flush=True)
    subprocess.run(
        ["cargo", "build", "--release", "--quiet", "--manifest-path", manifest],
        check=True,
    )
    rng = random.Random(seed)
    for case in CASES:
        print(f"case {case}", end=" ", flush=True)
        check_case(*case, rng)
        print("ok", flush=True)


if __name__ == "__main__":
    run()
    print(f"{len(CASES)} cases pass")
