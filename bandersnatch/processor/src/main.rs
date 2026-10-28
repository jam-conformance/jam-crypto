use std::{collections::HashMap, fs, path::PathBuf};

use ark_vrf::{
    CanonicalDeserializeExact,
    reexports::ark_serialize::{CanonicalDeserialize, CanonicalSerialize},
    suites::bandersnatch::{
        Input, PcsParams, Public, RingContext, RingProof, RingSetup, ScalarField, Secret,
        ThinProof, VrfIo,
    },
};

type Vector = HashMap<String, String>;

fn data_path(relative: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join(relative)
}

fn load_vectors(scheme: &str) -> Vec<Vector> {
    let path = data_path(&format!("vectors/bandersnatch_sha-512_ell2_{scheme}.json"));
    serde_json::from_slice(&fs::read(path).unwrap()).unwrap()
}

fn load_pcs_params() -> PcsParams {
    let bytes = fs::read(data_path("srs/zcash-srs-2-11-uncompressed.bin")).unwrap();
    PcsParams::deserialize_uncompressed_unchecked(&bytes[..]).unwrap()
}

fn field(vector: &Vector, name: &str) -> Vec<u8> {
    hex::decode(&vector[name]).unwrap()
}

fn fields(vector: &Vector, names: &[&str]) -> Vec<u8> {
    names.iter().flat_map(|name| field(vector, name)).collect()
}

fn encode(value: &impl CanonicalSerialize) -> Vec<u8> {
    let mut bytes = Vec::new();
    value.serialize_compressed(&mut bytes).unwrap();
    bytes
}

fn decode<T: CanonicalDeserialize>(bytes: &[u8]) -> T {
    T::deserialize_compressed_exact(bytes).unwrap()
}

struct Common {
    secret: Secret,
    public: Public,
    io: VrfIo,
    ad: Vec<u8>,
}

fn check_common(vector: &Vector) -> Common {
    let secret = Secret::from_scalar(decode::<ScalarField>(&field(vector, "sk")));
    let public = decode(&field(vector, "pk"));
    assert_eq!(secret.public(), public, "pk");

    let input = Input::new(&field(vector, "alpha")).unwrap();
    assert_eq!(encode(&input.point()), field(vector, "h"), "h");

    let io = secret.vrf_io(input);
    assert_eq!(encode(&io.output), field(vector, "gamma"), "gamma");
    assert_eq!(
        io.output.hash::<32>().to_vec(),
        field(vector, "beta"),
        "beta"
    );

    let ad = field(vector, "ad");
    Common {
        secret,
        public,
        io,
        ad,
    }
}

fn check_thin(vector: &Vector) {
    let Common {
        secret,
        public,
        io,
        ad,
    } = check_common(vector);
    let proof_bytes = fields(vector, &["proof_r", "proof_s"]);

    let proof: ThinProof = decode(&proof_bytes);
    public
        .verify_thin(io, &ad, &proof)
        .expect("thin proof verification");

    assert_eq!(
        encode(&secret.prove_thin(io, &ad)),
        proof_bytes,
        "thin proof"
    );
}

fn check_ring(vector: &Vector, pcs_params: &PcsParams) {
    let Common {
        secret,
        public,
        io,
        ad,
    } = check_common(vector);
    let proof_bytes = fields(
        vector,
        &[
            "proof_pk_com",
            "proof_r",
            "proof_ok",
            "proof_s",
            "proof_sb",
            "ring_proof",
        ],
    );

    let ring_pks: Vec<Public> = field(vector, "ring_pks").chunks(32).map(decode).collect();
    let ring_setup = RingSetup::from_pcs_params(ring_pks.len(), pcs_params.clone()).unwrap();
    let (prover_key, verifier_key) = ring_setup.keys(&ring_pks).unwrap();
    let commitment = encode(&verifier_key.commitment());
    assert_eq!(commitment, field(vector, "ring_pks_com"), "ring_pks_com");

    let proof: RingProof = decode(&proof_bytes);
    let verifier = ring_setup.ring_context().ring_verifier(verifier_key);
    proof
        .verify(io, &ad, &verifier)
        .expect("ring proof verification");

    // The vectors come from a prover without column blinding, so that the proof is reproducible.
    let signer = ring_pks.iter().position(|pk| *pk == public).unwrap();
    let prover =
        RingContext::new_without_blinding(ring_pks.len()).into_ring_prover(prover_key, signer);
    assert_eq!(
        encode(&secret.prove_ring(io, &ad, &prover)),
        proof_bytes,
        "ring proof"
    );

    let (_, blinding) = secret.prove_pedersen(io, &ad);
    assert_eq!(encode(&blinding), field(vector, "blinding"), "blinding");
}

fn run(scheme: &str, check: impl Fn(&Vector)) {
    for vector in load_vectors(scheme) {
        println!("{}", vector["comment"]);
        check(&vector);
    }
}

fn main() {
    let pcs_params = load_pcs_params();
    run("thin", check_thin);
    run("ring", |vector| check_ring(vector, &pcs_params));
    println!("All vectors ok");
}
