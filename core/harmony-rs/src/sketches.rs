use std::collections::{BTreeMap, BTreeSet};
use std::hash::{Hash, Hasher};

fn hash64(seed: u64, value: &str) -> u64 {
    // Deterministic FNV-1a with seed diffusion. It is not cryptographic; these
    // structures need stable universal-ish hashing, not secrecy.
    let mut hash = 0xcbf29ce484222325_u64 ^ seed.wrapping_mul(0x9e3779b97f4a7c15);
    for byte in value.as_bytes() {
        hash ^= *byte as u64;
        hash = hash.wrapping_mul(0x100000001b3);
        hash ^= hash >> 32;
    }
    hash
}

pub fn minhash_signature(values: &[String], permutations: usize) -> Vec<u64> {
    let unique: BTreeSet<&String> = values.iter().collect();
    if unique.is_empty() {
        return Vec::new();
    }
    (0..permutations.max(1))
        .map(|seed| {
            unique
                .iter()
                .map(|value| hash64(seed as u64, value))
                .min()
                .unwrap_or(0)
        })
        .collect()
}

pub fn minhash_similarity(left: &[u64], right: &[u64]) -> f64 {
    if left.is_empty() && right.is_empty() {
        return 1.0;
    }
    if left.is_empty() || right.is_empty() {
        return 0.0;
    }
    let size = left.len().min(right.len());
    let equal = left
        .iter()
        .zip(right)
        .take(size)
        .filter(|(a, b)| a == b)
        .count();
    equal as f64 / size as f64
}

pub fn dependency_novelty(
    target: &[String],
    peers: &[Vec<String>],
    permutations: usize,
) -> f64 {
    let signature = minhash_signature(target, permutations);
    if signature.is_empty() {
        return 0.0;
    }
    let maximum_similarity = peers
        .iter()
        .map(|peer| minhash_signature(peer, permutations))
        .filter(|signature| !signature.is_empty())
        .map(|other| minhash_similarity(&signature, &other))
        .fold(0.0_f64, f64::max);
    (1.0 - maximum_similarity).clamp(0.0, 1.0)
}

#[derive(Debug, Clone)]
pub struct BloomFilter {
    bits: usize,
    hashes: usize,
    bitmap: Vec<u8>,
    count: usize,
}

impl BloomFilter {
    pub fn new(bits: usize, hashes: usize) -> Self {
        assert!(bits > 0 && hashes > 0);
        Self {
            bits,
            hashes,
            bitmap: vec![0; (bits + 7) / 8],
            count: 0,
        }
    }

    fn positions(&self, value: &str) -> impl Iterator<Item = usize> + '_ {
        let hashes = self.hashes;
        (0..hashes).map(move |seed| (hash64(seed as u64, value) as usize) % self.bits)
    }

    pub fn insert(&mut self, value: &str) {
        let positions: Vec<usize> = self.positions(value).collect();
        for position in positions {
            self.bitmap[position / 8] |= 1 << (position % 8);
        }
        self.count += 1;
    }

    pub fn contains(&self, value: &str) -> bool {
        self.positions(value)
            .all(|position| self.bitmap[position / 8] & (1 << (position % 8)) != 0)
    }

    pub fn estimated_false_positive_rate(&self) -> f64 {
        (1.0 - (-(self.hashes as f64) * self.count as f64 / self.bits as f64).exp())
            .powi(self.hashes as i32)
    }
}

#[derive(Debug, Clone)]
pub struct CountMinSketch {
    width: usize,
    depth: usize,
    table: Vec<Vec<u64>>,
}

impl CountMinSketch {
    pub fn new(width: usize, depth: usize) -> Self {
        assert!(width > 0 && depth > 0);
        Self {
            width,
            depth,
            table: vec![vec![0; width]; depth],
        }
    }

    pub fn add(&mut self, key: &str, count: u64) {
        for seed in 0..self.depth {
            let index = (hash64(seed as u64, key) as usize) % self.width;
            self.table[seed][index] = self.table[seed][index].saturating_add(count);
        }
    }

    pub fn estimate(&self, key: &str) -> u64 {
        (0..self.depth)
            .map(|seed| {
                let index = (hash64(seed as u64, key) as usize) % self.width;
                self.table[seed][index]
            })
            .min()
            .unwrap_or(0)
    }

    pub fn merge(&mut self, other: &Self) -> Result<(), &'static str> {
        if self.width != other.width || self.depth != other.depth {
            return Err("sketch dimensions must match");
        }
        for row in 0..self.depth {
            for column in 0..self.width {
                self.table[row][column] = self.table[row][column]
                    .saturating_add(other.table[row][column]);
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct HyperLogLog {
    precision: u8,
    registers: Vec<u8>,
}

impl HyperLogLog {
    pub fn new(precision: u8) -> Self {
        assert!((4..=16).contains(&precision));
        Self {
            precision,
            registers: vec![0; 1usize << precision],
        }
    }

    pub fn insert(&mut self, value: &str) {
        let hashed = hash64(0x484c4c, value);
        let index_mask = (1u64 << self.precision) - 1;
        let index = (hashed & index_mask) as usize;
        let remainder = hashed >> self.precision;
        let width = 64 - self.precision as u32;
        let rank = if remainder == 0 {
            width + 1
        } else {
            remainder.leading_zeros().saturating_sub(self.precision as u32) + 1
        };
        self.registers[index] = self.registers[index].max(rank.min(255) as u8);
    }

    pub fn estimate(&self) -> f64 {
        let m = self.registers.len() as f64;
        let alpha = match self.registers.len() {
            16 => 0.673,
            32 => 0.697,
            64 => 0.709,
            _ => 0.7213 / (1.0 + 1.079 / m),
        };
        let harmonic = self
            .registers
            .iter()
            .map(|register| 2.0_f64.powi(-(*register as i32)))
            .sum::<f64>();
        let mut estimate = alpha * m * m / harmonic.max(1e-12);

        let zeros = self.registers.iter().filter(|register| **register == 0).count();
        if estimate <= 2.5 * m && zeros > 0 {
            estimate = m * (m / zeros as f64).ln();
        }
        estimate
    }

    pub fn merge(&mut self, other: &Self) -> Result<(), &'static str> {
        if self.precision != other.precision {
            return Err("precision must match");
        }
        for (left, right) in self.registers.iter_mut().zip(&other.registers) {
            *left = (*left).max(*right);
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HeavyHitter {
    pub key: String,
    pub estimate: u64,
    pub error: u64,
}

#[derive(Debug, Clone)]
pub struct SpaceSaving {
    capacity: usize,
    counters: BTreeMap<String, (u64, u64)>,
}

impl SpaceSaving {
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0);
        Self {
            capacity,
            counters: BTreeMap::new(),
        }
    }

    pub fn add(&mut self, key: &str, count: u64) {
        assert!(count > 0);
        if let Some((estimate, _)) = self.counters.get_mut(key) {
            *estimate = estimate.saturating_add(count);
            return;
        }
        if self.counters.len() < self.capacity {
            self.counters.insert(key.to_owned(), (count, 0));
            return;
        }

        let victim = self
            .counters
            .iter()
            .min_by_key(|(key, (estimate, _))| (*estimate, (*key).clone()))
            .map(|(key, value)| (key.clone(), *value))
            .expect("capacity is positive");
        self.counters.remove(&victim.0);
        self.counters.insert(
            key.to_owned(),
            (victim.1 .0.saturating_add(count), victim.1 .0),
        );
    }

    pub fn heavy_hitters(&self) -> Vec<HeavyHitter> {
        let mut items: Vec<HeavyHitter> = self
            .counters
            .iter()
            .map(|(key, (estimate, error))| HeavyHitter {
                key: key.clone(),
                estimate: *estimate,
                error: *error,
            })
            .collect();
        items.sort_by(|a, b| {
            b.estimate
                .cmp(&a.estimate)
                .then_with(|| a.key.cmp(&b.key))
        });
        items
    }
}

pub fn exact_jaccard(left: &[String], right: &[String]) -> f64 {
    let a: BTreeSet<&String> = left.iter().collect();
    let b: BTreeSet<&String> = right.iter().collect();
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    let intersection = a.intersection(&b).count();
    let union = a.union(&b).count();
    intersection as f64 / union.max(1) as f64
}

pub fn frequency_table(values: &[String]) -> BTreeMap<String, u64> {
    let mut out = BTreeMap::new();
    for value in values {
        *out.entry(value.clone()).or_insert(0) += 1;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn minhash_tracks_similarity() {
        let a = vec!["a".into(), "b".into(), "c".into()];
        let b = a.clone();
        let c = vec!["x".into(), "y".into()];
        let sa = minhash_signature(&a, 64);
        assert_eq!(minhash_similarity(&sa, &minhash_signature(&b, 64)), 1.0);
        assert!(minhash_similarity(&sa, &minhash_signature(&c, 64)) < 0.5);
    }

    #[test]
    fn bloom_has_no_false_negatives_for_inserted_items() {
        let mut filter = BloomFilter::new(2048, 5);
        for value in ["a", "b", "c", "d"] {
            filter.insert(value);
            assert!(filter.contains(value));
        }
    }

    #[test]
    fn count_min_never_underestimates() {
        let mut sketch = CountMinSketch::new(128, 5);
        for _ in 0..20 {
            sketch.add("hot", 1);
        }
        assert!(sketch.estimate("hot") >= 20);
    }

    #[test]
    fn hyperloglog_is_reasonable() {
        let mut hll = HyperLogLog::new(10);
        for index in 0..1000 {
            hll.insert(&format!("repo-{index}"));
        }
        let estimate = hll.estimate();
        assert!((estimate - 1000.0).abs() / 1000.0 < 0.25);
    }

    #[test]
    fn space_saving_keeps_heavy_hitter() {
        let mut sketch = SpaceSaving::new(4);
        for _ in 0..30 {
            sketch.add("hot", 1);
        }
        for value in ["a", "b", "c", "d", "e", "f"] {
            sketch.add(value, 1);
        }
        assert_eq!(sketch.heavy_hitters()[0].key, "hot");
    }
}
