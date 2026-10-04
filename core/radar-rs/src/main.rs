use serde::Deserialize;
use std::io::{self, BufRead};

#[derive(Deserialize)]
struct Event {
    source: String,
    repository: String,
    observed_at: String,
    event_type: String,
    semantic_impact: f64,
}

fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash = 0xcbf29ce484222325u64;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x100000001b3);
    }
    hash
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    for line in io::stdin().lock().lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let event: Event = serde_json::from_str(&line)?;
        let canonical = format!(
            "{}\0{}\0{}\0{}\0{:.6}",
            event.source,
            event.repository,
            event.observed_at,
            event.event_type,
            event.semantic_impact
        );
        println!("{:016x}\t{}", fnv1a64(canonical.as_bytes()), event.repository);
    }
    Ok(())
}
