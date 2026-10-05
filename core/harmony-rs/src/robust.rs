use crate::clamp01;

fn finite(values: &[f64]) -> Vec<f64> {
    values.iter().copied().filter(|value| value.is_finite()).collect()
}

pub fn median(values: &[f64]) -> f64 {
    let mut xs = finite(values);
    if xs.is_empty() {
        return 0.0;
    }
    xs.sort_by(f64::total_cmp);
    let middle = xs.len() / 2;
    if xs.len() % 2 == 0 {
        (xs[middle - 1] + xs[middle]) / 2.0
    } else {
        xs[middle]
    }
}

pub fn mad(values: &[f64], center: Option<f64>) -> f64 {
    let xs = finite(values);
    if xs.is_empty() {
        return 1.0;
    }
    let center = center.unwrap_or_else(|| median(&xs));
    let deviations: Vec<f64> = xs.iter().map(|value| (value - center).abs()).collect();
    (1.4826 * median(&deviations)).max(1e-9)
}

pub fn huber_location(values: &[f64], delta: f64, iterations: usize) -> f64 {
    let xs = finite(values);
    if xs.is_empty() {
        return 0.0;
    }
    let mut location = median(&xs);
    let scale = mad(&xs, Some(location));
    if scale <= 1e-12 {
        return location;
    }

    for _ in 0..iterations.max(1) {
        let threshold = delta.max(1e-6) * scale;
        let mut numerator = 0.0;
        let mut denominator = 0.0;
        for value in &xs {
            let residual = *value - location;
            let absolute = residual.abs();
            let weight = if absolute <= threshold {
                1.0
            } else {
                threshold / absolute.max(1e-12)
            };
            numerator += weight * *value;
            denominator += weight;
        }
        let updated = numerator / denominator.max(1e-12);
        if (updated - location).abs() <= 1e-9 * location.abs().max(1.0) {
            return updated;
        }
        location = updated;
    }
    location
}

pub fn hampel_outlier_fraction(values: &[f64], threshold: f64) -> f64 {
    let xs = finite(values);
    if xs.is_empty() {
        return 0.0;
    }
    let center = median(&xs);
    let scale = mad(&xs, Some(center));
    if scale <= 1e-12 {
        return 0.0;
    }
    let outliers = xs
        .iter()
        .filter(|value| (**value - center).abs() > threshold.max(0.0) * scale)
        .count();
    outliers as f64 / xs.len() as f64
}

pub fn theil_sen_slope(values: &[f64]) -> f64 {
    let xs = finite(values);
    if xs.len() < 2 {
        return 0.0;
    }
    let mut slopes = Vec::with_capacity(xs.len() * (xs.len() - 1) / 2);
    for left in 0..xs.len() - 1 {
        for right in left + 1..xs.len() {
            slopes.push((xs[right] - xs[left]) / (right - left) as f64);
        }
    }
    median(&slopes)
}

pub fn winsorized_variance(values: &[f64], clip_z: f64) -> f64 {
    let xs = finite(values);
    if xs.len() < 2 {
        return 0.0;
    }
    let center = huber_location(&xs, 1.345, 16);
    let scale = mad(&xs, Some(center));
    let low = center - clip_z.max(0.0) * scale;
    let high = center + clip_z.max(0.0) * scale;
    let clipped: Vec<f64> = xs.iter().map(|value| value.clamp(low, high)).collect();
    let mean = clipped.iter().sum::<f64>() / clipped.len() as f64;
    clipped
        .iter()
        .map(|value| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / (clipped.len() - 1) as f64
}

pub fn trimmed_mean(values: &[f64], trim_fraction: f64) -> f64 {
    let mut xs = finite(values);
    if xs.is_empty() {
        return 0.0;
    }
    xs.sort_by(f64::total_cmp);
    let trim = ((xs.len() as f64 * trim_fraction.clamp(0.0, 0.49)).floor() as usize)
        .min(xs.len() / 2);
    let slice = &xs[trim..xs.len() - trim];
    slice.iter().sum::<f64>() / slice.len() as f64
}

pub fn robust_z_score(value: f64, history: &[f64]) -> f64 {
    if history.is_empty() {
        return 0.0;
    }
    let center = median(history);
    let scale = mad(history, Some(center));
    (value - center) / scale.max(1e-9)
}

pub fn bounded_robust_activity(features: &[f64]) -> f64 {
    if features.is_empty() {
        return 0.0;
    }
    let location = huber_location(features, 1.345, 16);
    let outliers = hampel_outlier_fraction(features, 3.0);
    let trimmed = trimmed_mean(features, 0.1);
    let blend = 0.58 * location + 0.42 * trimmed;
    clamp01(crate::stable_sigmoid(blend) * (1.0 - 0.12 * outliers))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn median_works_for_even_and_odd() {
        assert_eq!(median(&[3.0, 1.0, 2.0]), 2.0);
        assert_eq!(median(&[4.0, 1.0, 3.0, 2.0]), 2.5);
    }

    #[test]
    fn huber_resists_extreme_value() {
        let xs = [1.0, 1.1, 0.9, 1.05, 100.0];
        let robust = huber_location(&xs, 1.345, 20);
        let mean = xs.iter().sum::<f64>() / xs.len() as f64;
        assert!((robust - 1.0).abs() < (mean - 1.0).abs());
    }

    #[test]
    fn theil_sen_detects_direction() {
        assert!(theil_sen_slope(&[1.0, 2.0, 3.0, 4.0]) > 0.9);
        assert!(theil_sen_slope(&[4.0, 3.0, 2.0, 1.0]) < -0.9);
    }

    #[test]
    fn activity_is_bounded() {
        let value = bounded_robust_activity(&[0.1, 0.2, 0.3, 9.0]);
        assert!((0.0..=1.0).contains(&value));
    }
}
