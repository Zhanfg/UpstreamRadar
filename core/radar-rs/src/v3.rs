pub fn clamp01(value: f64) -> f64 {
    value.clamp(0.0, 1.0)
}

pub fn bernoulli_kl(q: f64, p: f64) -> f64 {
    let eps = 1e-12;
    let q = q.clamp(eps, 1.0 - eps);
    let p = p.clamp(eps, 1.0 - eps);
    q * (q / p).ln() + (1.0 - q) * ((1.0 - q) / (1.0 - p)).ln()
}

pub fn bayesian_surprise(empirical: f64, predicted: f64) -> f64 {
    clamp01(1.0 - (-3.4 * bernoulli_kl(empirical, predicted)).exp())
}

pub fn cvar(values: &[f64], quantile: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut xs: Vec<f64> = values.iter().copied().map(clamp01).collect();
    xs.sort_by(|a, b| a.total_cmp(b));
    let q = quantile.clamp(0.5, 0.999_999);
    let start = ((xs.len() as f64 * q).floor() as usize).min(xs.len() - 1);
    xs[start..].iter().sum::<f64>() / (xs.len() - start) as f64
}

pub fn risk_adjusted(utility: f64, tail_risk: f64, reliability: f64) -> f64 {
    let risk = clamp01(tail_risk);
    let trust = clamp01(reliability);
    utility.max(0.0) * (1.0 - 0.11 * risk) * (0.82 + 0.18 * trust)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn surprise_is_bounded() {
        let value = bayesian_surprise(0.9, 0.2);
        assert!((0.0..=1.0).contains(&value));
        assert!(value > bayesian_surprise(0.21, 0.2));
    }

    #[test]
    fn cvar_tracks_tail() {
        assert!(cvar(&[0.1, 0.2, 0.3, 0.9], 0.75) >= 0.9);
    }
}
