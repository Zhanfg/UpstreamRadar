use crate::clamp01;
use std::f64::consts::LN_2;

const EPS: f64 = 1e-12;

fn normalize(values: &[f64]) -> Vec<f64> {
    if values.is_empty() {
        return Vec::new();
    }
    let positive: Vec<f64> = values.iter().map(|value| value.max(0.0)).collect();
    let total = positive.iter().sum::<f64>();
    if total <= EPS {
        return vec![1.0 / positive.len() as f64; positive.len()];
    }
    positive.iter().map(|value| *value / total).collect()
}

pub fn entropy(values: &[f64]) -> f64 {
    normalize(values)
        .iter()
        .filter(|value| **value > EPS)
        .map(|value| -value * value.ln() / LN_2)
        .sum()
}

fn kl_divergence(left: &[f64], right: &[f64]) -> f64 {
    left.iter()
        .zip(right)
        .filter(|(a, b)| **a > EPS && **b > EPS)
        .map(|(a, b)| a * (a / b).ln() / LN_2)
        .sum()
}

pub fn jensen_shannon(left: &[f64], right: &[f64]) -> f64 {
    let size = left.len().max(right.len());
    if size == 0 {
        return 0.0;
    }
    let mut l = left.to_vec();
    let mut r = right.to_vec();
    l.resize(size, 0.0);
    r.resize(size, 0.0);
    let l = normalize(&l);
    let r = normalize(&r);
    let midpoint: Vec<f64> = l.iter().zip(&r).map(|(a, b)| (a + b) / 2.0).collect();
    clamp01(0.5 * kl_divergence(&l, &midpoint) + 0.5 * kl_divergence(&r, &midpoint))
}

fn quantile(sorted: &[f64], q: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    if sorted.len() == 1 {
        return sorted[0];
    }
    let position = q.clamp(0.0, 1.0) * (sorted.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = (lower + 1).min(sorted.len() - 1);
    let fraction = position - lower as f64;
    sorted[lower] * (1.0 - fraction) + sorted[upper] * fraction
}

pub fn wasserstein_1d(left: &[f64], right: &[f64]) -> f64 {
    if left.is_empty() && right.is_empty() {
        return 0.0;
    }
    if left.is_empty() || right.is_empty() {
        return 1.0;
    }
    let mut a: Vec<f64> = left.iter().map(|value| clamp01(*value)).collect();
    let mut b: Vec<f64> = right.iter().map(|value| clamp01(*value)).collect();
    a.sort_by(f64::total_cmp);
    b.sort_by(f64::total_cmp);

    let samples = a.len().max(b.len()).max(2);
    let mut total = 0.0;
    for index in 0..samples {
        let q = index as f64 / (samples - 1) as f64;
        total += (quantile(&a, q) - quantile(&b, q)).abs();
    }
    clamp01(total / samples as f64)
}

fn median(mut values: Vec<f64>) -> f64 {
    if values.is_empty() {
        return 0.1;
    }
    values.sort_by(f64::total_cmp);
    let middle = values.len() / 2;
    if values.len() % 2 == 0 {
        (values[middle - 1] + values[middle]) / 2.0
    } else {
        values[middle]
    }
}

pub fn maximum_mean_discrepancy(left: &[f64], right: &[f64], bandwidth: Option<f64>) -> f64 {
    if left.is_empty() && right.is_empty() {
        return 0.0;
    }
    if left.is_empty() || right.is_empty() {
        return 1.0;
    }
    let a: Vec<f64> = left.iter().map(|value| clamp01(*value)).collect();
    let b: Vec<f64> = right.iter().map(|value| clamp01(*value)).collect();

    let sigma = bandwidth.unwrap_or_else(|| {
        let combined: Vec<f64> = a.iter().chain(&b).copied().collect();
        let mut distances = Vec::new();
        for i in 0..combined.len().saturating_sub(1) {
            for j in i + 1..combined.len() {
                let distance = (combined[i] - combined[j]).abs();
                if distance > EPS {
                    distances.push(distance);
                }
            }
        }
        median(distances)
    }).max(1e-6);

    let kernel = |x: f64, y: f64| {
        let distance = x - y;
        (-(distance * distance) / (2.0 * sigma * sigma)).exp()
    };

    let aa = a.iter().flat_map(|x| a.iter().map(move |y| kernel(*x, *y))).sum::<f64>()
        / (a.len() * a.len()) as f64;
    let bb = b.iter().flat_map(|x| b.iter().map(move |y| kernel(*x, *y))).sum::<f64>()
        / (b.len() * b.len()) as f64;
    let ab = a.iter().flat_map(|x| b.iter().map(move |y| kernel(*x, *y))).sum::<f64>()
        / (a.len() * b.len()) as f64;
    clamp01(((aa + bb - 2.0 * ab).max(0.0) / 2.0).sqrt())
}

fn histogram(segment: &[f64], bins: usize) -> Vec<f64> {
    let mut out = vec![0.0; bins.max(1)];
    for value in segment {
        let index = ((clamp01(*value) * out.len() as f64).floor() as usize).min(out.len() - 1);
        out[index] += 1.0;
    }
    out
}

pub fn distribution_shift(values: &[f64]) -> (f64, Vec<(&'static str, f64)>) {
    let xs: Vec<f64> = values.iter().map(|value| clamp01(*value)).collect();
    if xs.len() < 4 {
        return (0.0, vec![("jsd", 0.0), ("wasserstein", 0.0), ("mmd", 0.0)]);
    }
    let split = (xs.len() / 2).max(2).min(xs.len() - 1);
    let older = &xs[..split];
    let recent = &xs[split..];

    let js = jensen_shannon(&histogram(older, 4), &histogram(recent, 4));
    let wasserstein = wasserstein_1d(older, recent);
    let mmd = maximum_mean_discrepancy(older, recent, None);
    let votes = vec![("jsd", js), ("wasserstein", wasserstein), ("mmd", mmd)];
    let max = votes.iter().map(|(_, value)| *value).fold(0.0_f64, f64::max);
    let min = votes.iter().map(|(_, value)| *value).fold(1.0_f64, f64::min);
    let disagreement = max - min;
    let consensus = clamp01((0.42 * js + 0.30 * wasserstein + 0.28 * mmd)
        * (1.0 - 0.12 * disagreement));
    (consensus, votes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn jsd_is_symmetric() {
        let a = [9.0, 1.0, 0.0, 0.0];
        let b = [0.0, 0.0, 1.0, 9.0];
        assert!((jensen_shannon(&a, &b) - jensen_shannon(&b, &a)).abs() < 1e-12);
    }

    #[test]
    fn distances_detect_separation() {
        let a = [0.0, 0.1, 0.2];
        let b = [0.8, 0.9, 1.0];
        assert!(wasserstein_1d(&a, &b) > 0.6);
        assert!(maximum_mean_discrepancy(&a, &b, None) > 0.4);
    }

    #[test]
    fn identical_distribution_has_low_shift() {
        let xs = [0.1, 0.2, 0.1, 0.2, 0.1, 0.2, 0.1, 0.2];
        let (score, _) = distribution_shift(&xs);
        assert!(score < 0.2);
    }
}
