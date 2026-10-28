//! Encodes and decodes with reed-solomon-simd. Shards are hex strings, one per line.
//!
//! crate-cli encode <original_count> <recovery_count>
//!     stdin: the original shards; stdout: the recovery shards.
//! crate-cli decode <original_count> <recovery_count>
//!     stdin: "original <index> <shard>" or "recovery <index> <shard>";
//!     stdout: "<index> <shard>" for each restored original shard.

use std::io::Read;

fn from_hex(text: &str) -> Vec<u8> {
    (0..text.len())
        .step_by(2)
        .map(|start| u8::from_str_radix(&text[start..start + 2], 16).expect("hex shard"))
        .collect()
}

fn to_hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn main() -> Result<(), reed_solomon_simd::Error> {
    let args: Vec<String> = std::env::args().collect();
    let usage = "usage: crate-cli encode|decode <original_count> <recovery_count>";
    assert_eq!(args.len(), 4, "{usage}");
    let original_count: usize = args[2].parse().expect(usage);
    let recovery_count: usize = args[3].parse().expect(usage);

    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).expect("stdin");
    let lines = input.lines().filter(|line| !line.is_empty());

    match args[1].as_str() {
        "encode" => {
            let original: Vec<Vec<u8>> = lines.map(from_hex).collect();
            for shard in reed_solomon_simd::encode(original_count, recovery_count, &original)? {
                println!("{}", to_hex(&shard));
            }
        }
        "decode" => {
            let mut original = Vec::new();
            let mut recovery = Vec::new();
            for line in lines {
                let fields: Vec<&str> = line.split(' ').collect();
                let shard = (fields[1].parse::<usize>().expect("index"), from_hex(fields[2]));
                match fields[0] {
                    "original" => original.push(shard),
                    "recovery" => recovery.push(shard),
                    kind => panic!("unknown shard kind {kind}"),
                }
            }
            let restored = reed_solomon_simd::decode(original_count, recovery_count, original, recovery)?;
            for (index, shard) in restored {
                println!("{index} {}", to_hex(&shard));
            }
        }
        command => panic!("unknown command {command}; {usage}"),
    }
    Ok(())
}
