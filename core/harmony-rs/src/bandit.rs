use crate::clamp01;

const EPS: f64 = 1e-12;

pub fn bernoulli_kl(p0: f64, q0: f64) -> f64 {
    let p = p0.clamp(EPS, 1.0 - EPS);
    let q = q0.clamp(EPS, 1.0 - EPS);
    p * (p / q).ln() + (1.0 - p) * ((1.0 - p) / (1.0 - q)).ln()
}

pub fn ucb_v(mean: f64, variance: f64, pulls: u32, total_pulls: u32) -> f64 {
    if pulls == 0 {
        return 1.0;
    }
    let pulls = pulls as f64;
    let log_term = (total_pulls.max(2) as f64).ln();
    let bonus = (2.0 * variance.max(0.0) * log_term / pulls).sqrt()
        + 3.0 * log_term / pulls;
    clamp01(mean + bonus)
}

pub fn kl_ucb(mean: f64, pulls: u32, total_pulls: u32, precision: f64) -> f64 {
    let mean = clamp01(mean);
    if pulls == 0 {
        return 1.0;
    }
    let t = total_pulls.max(2) as f64;
    let budget = (t.ln() + 3.0 * t.ln().max(1.0).ln()) / pulls as f64;
    let mut low = mean;
    let mut high = 1.0 - EPS;
    while high - low > precision.max(1e-12) {
        let middle = (low + high) / 2.0;
        if bernoulli_kl(mean, middle) <= budget {
            low = middle;
        } else {
            high = middle;
        }
    }
    clamp01(low)
}

fn log_gamma(value: f64) -> f64 {
    // Lanczos approximation for positive arguments.
    const COEFFICIENTS: [f64; 9] = [
        0.999_999_999_999_809_9,
        676.520_368_121_885_1,
        -1_259.139_216_722_402_8,
        771.323_428_777_653_1,
        -176.615_029_162_140_6,
        12.507_343_278_686_905,
        -0.138_571_095_265_720_12,
        9.984_369_578_019_572e-6,
        1.505_632_735_149_311_6e-7,
    ];
    if value < 0.5 {
        return std::f64::consts::PI.ln()
            - (std::f64::consts::PI * value).sin().ln()
            - log_gamma(1.0 - value);
    }
    let z = value - 1.0;
    let mut x = COEFFICIENTS[0];
    for (index, coefficient) in COEFFICIENTS.iter().enumerate().skip(1) {
        x += coefficient / (z + index as f64);
    }
    let t = z + 7.5;
    0.5 * (2.0 * std::f64::consts::PI).ln()
        + (z + 0.5) * t.ln()
        - t
        + x.ln()
}

fn beta_continued_fraction(a: f64, b: f64, x: f64) -> f64 {
    let max_iterations = 200;
    let epsilon = 3e-14;
    let fpmin = 1e-300;

    let qab = a + b;
    let qap = a + 1.0;
    let qam = a - 1.0;
    let mut c = 1.0;
    let mut d = 1.0 - qab * x / qap;
    if d.abs() < fpmin {
        d = fpmin;
    }
    d = 1.0 / d;
    let mut h = d;

    for m in 1..=max_iterations {
        let m2 = 2 * m;
        let mut aa = m as f64 * (b - m as f64) * x
            / ((qam + m2 as f64) * (a + m2 as f64));

        d = 1.0 + aa * d;
        if d.abs() < fpmin {
            d = fpmin;
        }
        c = 1.0 + aa / c;
        if c.abs() < fpmin {
            c = fpmin;
        }
        d = 1.0 / d;
        h *= d * c;

        aa = -(a + m as f64) * (qab + m as f64) * x
            / ((a + m2 as f64) * (qap + m2 as f64));
        d = 1.0 + aa * d;
        if d.abs() < fpmin {
            d = fpmin;
        }
        c = 1.0 + aa / c;
        if c.abs() < fpmin {
            c = fpmin;
        }
        d = 1.0 / d;
        let delta = d * c;
        h *= delta;
        if (delta - 1.0).abs() <= epsilon {
            break;
        }
    }
    h
}

pub fn regularized_beta(x: f64, a: f64, b: f64) -> f64 {
    let x = clamp01(x);
    assert!(a > 0.0 && b > 0.0, "beta parameters must be positive");
    if x <= 0.0 {
        return 0.0;
    }
    if x >= 1.0 {
        return 1.0;
    }

    let log_bt = log_gamma(a + b) - log_gamma(a) - log_gamma(b)
        + a * x.ln()
        + b * (1.0 - x).ln();
    let bt = log_bt.exp();

    if x < (a + 1.0) / (a + b + 2.0) {
        clamp01(bt * beta_continued_fraction(a, b, x) / a)
    } else {
        clamp01(1.0 - bt * beta_continued_fraction(b, a, 1.0 - x) / b)
    }
}

pub fn beta_quantile(probability: f64, alpha: f64, beta: f64, precision: f64) -> f64 {
    let probability = clamp01(probability);
    let mut low = 0.0;
    let mut high = 1.0;
    while high - low > precision.max(1e-10) {
        let middle = (low + high) / 2.0;
        if regularized_beta(middle, alpha, beta) < probability {
            low = middle;
        } else {
            high = middle;
        }
    }
    clamp01((low + high) / 2.0)
}

pub fn bayes_ucb(alpha: f64, beta: f64, total_pulls: u32) -> f64 {
    let total = total_pulls.max(2) as f64;
    beta_quantile(1.0 - 1.0 / total, alpha, beta, 1e-7)
}

pub fn discounted_count(observation_count: u32, freshness_hours: f64) -> f64 {
    let decay = 1.0 / (1.0 + freshness_hours.max(0.0).ln_1p());
    observation_count as f64 * decay
}

pub fn exploration_votes(
    hits: u32,
    misses: u32,
    observation_count: u32,
    variance: f64,
    total_observations: u32,
) -> Vec<(&'static str, f64)> {
    let pulls = observation_count.max(hits + misses);
    let mean = (hits as f64 + 0.5) / (hits + misses) as f64
        .mul_add(1.0, 1.0);
    let ucbv = ucb_v(mean, variance, pulls, total_observations);
    let kl = kl_ucb(mean, pulls, total_observations, 1e-7);
    let bayes = bayes_ucb(hits as f64 + 1.0, misses as f64 + 1.0, total_observations);
    let deficit = 1.0 / (1.0 + pulls as f64).sqrt();

    vec![
        ("ucb-v", ucbv),
        ("kl-ucb", kl),
        ("bayes-ucb", bayes),
        ("information-deficit", deficit),
    ]
}

pub fn exploration_consensus(
    hits: u32,
    misses: u32,
    observation_count: u32,
    variance: f64,
    total_observations: u32,
) -> (f64, f64) {
    let votes = exploration_votes(
        hits,
        misses,
        observation_count,
        variance,
        total_observations,
    );
    let mean = votes.iter().map(|(_, value)| *value).sum::<f64>() / votes.len() as f64;
    let maximum = votes.iter().map(|(_, value)| *value).fold(0.0_f64, f64::max);
    let minimum = votes.iter().map(|(_, value)| *value).fold(1.0_f64, f64::min);
    let disagreement = maximum - minimum;
    (clamp01(mean * (1.0 - 0.12 * disagreement)), clamp01(disagreement))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn beta_uniform_is_identity() {
        assert!((regularized_beta(0.5, 1.0, 1.0) - 0.5).abs() < 1e-6);
        assert!((beta_quantile(0.9, 1.0, 1.0, 1e-8) - 0.9).abs() < 1e-5);
    }

    #[test]
    fn indexes_are_bounded() {
        for score in [
            ucb_v(0.2, 0.05, 10, 100),
            kl_ucb(0.2, 10, 100, 1e-7),
            bayes_ucb(3.0, 7.0, 100),
        ] {
            assert!((0.0..=1.0).contains(&score));
        }
    }

    #[test]
    fn consensus_is_bounded() {
        let (score, disagreement) = exploration_consensus(4, 6, 10, 0.04, 100);
        assert!((0.0..=1.0).contains(&score));
        assert!((0.0..=1.0).contains(&disagreement));
    }
}
