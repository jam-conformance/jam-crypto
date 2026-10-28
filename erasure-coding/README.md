# JAM Erasure Coding

Python reference implementation of the Reed-Solomon erasure code of JAM, and the
JAM test vectors. The post
[Reed-Solomon Erasure Coding](https://datawok.net/post/reed-solomon) builds the
code from Lagrange interpolation over GF(2^16), and explains the choices of the
Rust crate [reed-solomon-simd](https://crates.io/crates/reed-solomon-simd).

The Python files and `crate-cli/` are the companion code of the post.
`reed_solomon.py` gives the same shards as reed-solomon-simd, byte for byte.

| File | Content |
| --- | --- |
| `reed_solomon.py` | Encoder and decoder. Python standard library only. |
| `test_compat.py` | Encodes and decodes random shards with `reed_solomon.py` and with reed-solomon-simd, and compares the results. |
| `crate-cli/` | Rust program that calls reed-solomon-simd for `test_compat.py`. |
| `test_jam.py` | The polkajam `erasure_shards` function on top of `reed_solomon.py`. For each vector, it encodes `data` and compares all of the `shards`. |
| `vectors/full/` | 1023 shards, recovery threshold 342, 6 vectors |
| `vectors/tiny/` | 6 shards, recovery threshold 3, 6 vectors |

## Vectors

Each JSON file holds the input `data` and the expected `shards`, in hex. The files
are dumps of the polkajam `erasure_shards` function. The data lengths are 3, 32,
100, 4096, 4104 and 10000 bytes.

## Run

    cd erasure-coding
    python3 test_jam.py
    python3 test_compat.py

`test_jam.py` takes about one minute. `test_compat.py` needs cargo. It builds
`crate-cli` first.
