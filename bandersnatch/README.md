# Bandersnatch VRF Test Vectors

Test vectors of the [Bandersnatch VRF specification](https://github.com/davxy/bandersnatch-vrfs-spec),
suite `Bandersnatch-SHA512-ELL2-v1`. Appendix C of the specification gives the
field schema. JAM uses only the Thin VRF and the Ring VRF, so this folder holds
only the vectors of these two schemes.

The files are copies of `assets/` of the specification. `ark-vrf` 0.6.1 generates
them, and they are byte-identical to `data/` of that crate.

| File | Content |
| --- | --- |
| `vectors/bandersnatch_sha-512_ell2_thin.json` | Thin VRF, 7 vectors |
| `vectors/bandersnatch_sha-512_ell2_ring.json` | Ring VRF, 7 vectors |
| `srs/zcash-srs-2-11-uncompressed.bin` | KZG reference string for the ring proof (Zcash powers of tau) |
| `processor/` | Rust program that checks the vectors with `ark-vrf` |

## Encoding

All values are hex strings without the `0x` prefix. A scalar is 32 bytes, little-endian.
A point is 32 bytes in compressed form. A proof is the concatenation of its `proof_*`
fields in the order of the file:

- Thin: `proof_r` `proof_s`
- Ring: `proof_pk_com` `proof_r` `proof_ok` `proof_s` `proof_sb` `ring_proof`. The
  first five fields are the Pedersen proof.

`ring_pks` is the concatenation of the ring keys. The `blinding` field is the Pedersen
blinding factor.

## Ring parameters

- The ring has 8 keys. The signer is at index 3.
- The domain size is |D| = 512, the smallest domain for 8 keys. Section 5 of the
  specification gives |D| = 2048 for JAM. The ring commitment and the ring proof
  depend on |D|, so a prover or verifier with |D| = 2048 does not reproduce
  `ring_pks_com` or `ring_proof`.
- The KZG parameters are the first 3·|D| + 1 G1 powers of the reference string.
- The prover runs without column blinding: the zk rows hold zeros. Thus the proof is
  deterministic, but it is not zero-knowledge. A verifier with blinding on accepts it.
  Never disable blinding in production.

## Processor

For each vector, the program:

1. Derives `pk`, `h`, `gamma` and `beta` from `sk` and `alpha`, and compares them with the vector.
2. Decodes the proof of the vector and verifies it.
3. Makes the proof again from `sk` and compares the bytes. It also compares the `blinding` factor.
4. Ring only: computes the commitment of `ring_pks` and compares it with `ring_pks_com`.

The program stops at the first mismatch.

    cd processor
    cargo run --release
