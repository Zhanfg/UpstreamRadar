use crate::clamp01;
use crate::robust::theil_sen_slope;

#[derive(Debug, Clone, PartialEq)]
pub struct BocpdResult {
    pub reset_probability: f64,
    pub expected_run_length: f64,
    pub posterior: Vec<f64>,
}

pub fn cusum_score(values: &[f64], drift: f64) -> f64 {
    let xs: Vec<f64> = values.iter().map(|value| clamp01(*value)).collect();
    if xs.len() < 2 {
        return 0.0;
    }
    let mean = xs.iter().sum::<f64>() / xs.len() as f64;
    let mut positive = 0.0_f64;
    let mut negative = 0.0_f64;
    let mut maximum = 0.0_f64;

    for value in xs {
        let residual = value - mean;
        positive = (positive + residual - drift).max(0.0);
        negative = (negative + residual + drift).min(0.0);
        maximum = maximum.max(positive).max(-negative);
    }
    clamp01(1.0 - (-2.4 * maximum).exp())
}

pub fn page_hinkley_score(values: &[f64], delta: f64, scale: f64) -> f64 {
    let xs: Vec<f64> = values.iter().map(|value| clamp01(*value)).collect();
    if xs.len() < 2 {
        return 0.0;
    }

    let mut running_mean = 0.0;
    let mut cumulative = 0.0_f64;
    let mut minimum = 0.0_f64;
    let mut peak = 0.0_f64;

    for (index, value) in xs.iter().enumerate() {
        let count = (index + 1) as f64;
        running_mean += (*value - running_mean) / count;
        cumulative += *value - running_mean - delta;
        minimum = minimum.min(cumulative);
        peak = peak.max(cumulative - minimum);
    }
    clamp01(1.0 - (-peak / scale.max(1e-9)).exp())
}

pub fn adwin_score(values: &[f64], delta: f64, min_window: usize) -> f64 {
    let xs: Vec<f64> = values.iter().map(|value| clamp01(*value)).collect();
    if xs.len() < min_window.saturating_mul(2).max(2) {
        return 0.0;
    }

    let mut prefix = Vec::with_capacity(xs.len() + 1);
    prefix.push(0.0);
    for value in &xs {
        let next = prefix.last().copied().unwrap_or(0.0) + *value;
        prefix.push(next);
    }

    let confidence = delta.clamp(1e-12, 0.5);
    let log_term = (4.0 / confidence).ln();
    let mut strongest = 0.0_f64;

    for cut in min_window..=xs.len() - min_window {
        let n0 = cut as f64;
        let n1 = (xs.len() - cut) as f64;
        let mean0 = prefix[cut] / n0;
        let mean1 = (prefix[xs.len()] - prefix[cut]) / n1;
        let epsilon = (0.5 * log_term * (1.0 / n0 + 1.0 / n1)).sqrt();
        let excess = (mean1 - mean0).abs() - epsilon;
        if excess > 0.0 {
            strongest = strongest.max(excess / (1.0 + epsilon));
        }
    }
    clamp01(strongest * 2.5)
}

pub fn bernoulli_bocpd(
    observations: &[u8],
    hazard: f64,
    prior_alpha: f64,
    prior_beta: f64,
    max_run_length: usize,
) -> BocpdResult {
    if observations.is_empty() {
        return BocpdResult {
            reset_probability: 0.0,
            expected_run_length: 0.0,
            posterior: vec![1.0],
        };
    }

    let hazard = hazard.clamp(1e-6, 0.95);
    let prior_alpha = prior_alpha.max(1e-9);
    let prior_beta = prior_beta.max(1e-9);

    let mut probabilities = vec![1.0_f64];
    let mut alphas = vec![prior_alpha];
    let mut betas = vec![prior_beta];

    for raw in observations {
        let observation = if *raw == 0 { 0.0 } else { 1.0 };
        let length = probabilities.len().min(max_run_length + 1);
        let next_size = (length + 1).min(max_run_length + 1);
        let mut next_probability = vec![0.0; next_size];
        let mut next_alpha = vec![prior_alpha; next_size];
        let mut next_beta = vec![prior_beta; next_size];

        let prior_predictive = if observation > 0.5 {
            prior_alpha / (prior_alpha + prior_beta)
        } else {
            prior_beta / (prior_alpha + prior_beta)
        };
        next_probability[0] = hazard * prior_predictive * probabilities[..length].iter().sum::<f64>();
        next_alpha[0] = prior_alpha + observation;
        next_beta[0] = prior_beta + (1.0 - observation);

        for run_length in 0..length {
            let target = run_length + 1;
            if target >= next_size {
                continue;
            }
            let alpha = alphas[run_length];
            let beta = betas[run_length];
            let predictive = if observation > 0.5 {
                alpha / (alpha + beta)
            } else {
                beta / (alpha + beta)
            };
            next_probability[target] =
                probabilities[run_length] * predictive * (1.0 - hazard);
            next_alpha[target] = alpha + observation;
            next_beta[target] = beta + (1.0 - observation);
        }

        let total = next_probability.iter().sum::<f64>();
        if total <= 1e-15 {
            next_probability.fill(0.0);
            next_probability[0] = 1.0;
        } else {
            for probability in &mut next_probability {
                *probability /= total;
            }
        }

        probabilities = next_probability;
        alphas = next_alpha;
        betas = next_beta;
    }

    let expected_run_length = probabilities
        .iter()
        .enumerate()
        .map(|(index, probability)| index as f64 * probability)
        .sum();

    BocpdResult {
        reset_probability: clamp01(probabilities[0]),
        expected_run_length,
        posterior: probabilities,
    }
}

pub fn robust_jump_score(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let prior = &values[..values.len() - 1];
    let center = crate::robust::median(prior);
    let scale = crate::robust::mad(prior, Some(center));
    clamp01((values[values.len() - 1] - center).abs() / (1.35 * scale.max(1e-9)))
}

pub fn trend_score(values: &[f64]) -> f64 {
    clamp01(theil_sen_slope(values).abs() * 4.0)
}

pub fn ensemble(
    impact_history: &[f64],
    change_history: &[u8],
) -> Vec<(&'static str, f64)> {
    let mut normalized: Vec<f64> = impact_history
        .iter()
        .map(|value| clamp01(*value / 10.0))
        .collect();
    if normalized.is_empty() {
        normalized = change_history
            .iter()
            .map(|value| if *value == 0 { 0.0 } else { 1.0 })
            .collect();
    }

    let bocpd = if change_history.is_empty() {
        0.0
    } else {
        bernoulli_bocpd(change_history, 0.08, 1.0, 1.0, 64).reset_probability
    };

    vec![
        ("cusum", cusum_score(&normalized, 0.02)),
        ("page-hinkley", page_hinkley_score(&normalized, 0.04, 1.25)),
        ("adwin", adwin_score(&normalized, 0.01, 3)),
        ("bocpd-beta", bocpd),
        ("robust-jump", robust_jump_score(&normalized)),
        ("theil-sen", trend_score(&normalized)),
    ]
}

pub fn ensemble_consensus(impact_history: &[f64], change_history: &[u8]) -> (f64, f64) {
    let votes = ensemble(impact_history, change_history);
    if votes.is_empty() {
        return (0.0, 0.0);
    }
    let mean = votes.iter().map(|(_, value)| *value).sum::<f64>() / votes.len() as f64;
    let variance = votes
        .iter()
        .map(|(_, value)| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / votes.len() as f64;
    let disagreement = clamp01(variance.sqrt() * 2.0);
    let consensus = clamp01(mean * (1.0 - 0.22 * disagreement));
    (consensus, disagreement)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detectors_respond_to_shift() {
        let stable = vec![0.1; 48];
        let shifted = [vec![0.1; 24], vec![0.9; 24]].concat();
        assert!(cusum_score(&shifted, 0.02) > cusum_score(&stable, 0.02));
        assert!(adwin_score(&shifted, 0.01, 3) > adwin_score(&stable, 0.01, 3));
    }

    #[test]
    fn bocpd_responds_to_regime_reset() {
        let stable = bernoulli_bocpd(&[0; 16], 0.08, 1.0, 1.0, 64);
        let shifted = bernoulli_bocpd(
            &[0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
            0.08,
            1.0,
            1.0,
            64,
        );
        assert!(shifted.reset_probability >= stable.reset_probability);
        assert!((shifted.posterior.iter().sum::<f64>() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn ensemble_is_bounded() {
        let (consensus, disagreement) = ensemble_consensus(
            &[1.0, 1.0, 2.0, 8.0, 9.0],
            &[0, 0, 0, 1, 1],
        );
        assert!((0.0..=1.0).contains(&consensus));
        assert!((0.0..=1.0).contains(&disagreement));
    }
}
