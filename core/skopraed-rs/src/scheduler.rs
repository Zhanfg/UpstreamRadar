use crate::bandit;
use crate::change;
use crate::graph::{self, Graph};
use crate::information;
use crate::model::{
    Candidate, GalleryEvidence, GalleryVote, MuseumEvidence, RepositorySignal,
    Schedule, SchedulerConfig,
};
use crate::optimization::{self, Item};
use crate::robust;
use crate::sketches;
use crate::{clamp01, stable_sigmoid};

use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone)]
pub struct SkopraedScheduler {
    config: SchedulerConfig,
}

impl Default for SkopraedScheduler {
    fn default() -> Self {
        Self::new(SchedulerConfig::default()).expect("default configuration is valid")
    }
}

impl SkopraedScheduler {
    pub fn new(config: SchedulerConfig) -> Result<Self, String> {
        config.validate()?;
        Ok(Self { config })
    }

    pub fn config(&self) -> &SchedulerConfig {
        &self.config
    }

    fn empirical_bayes_priors(
        &self,
        records: &[RepositorySignal],
    ) -> BTreeMap<String, (f64, f64)> {
        let global_hits: u32 = records.iter().map(|record| record.recent_change_hits).sum();
        let global_misses: u32 = records.iter().map(|record| record.recent_change_misses).sum();
        let global_rate =
            (global_hits as f64 + 1.0) / ((global_hits + global_misses) as f64 + 2.0);

        let mut by_ecosystem: BTreeMap<String, (u32, u32)> = BTreeMap::new();
        for record in records {
            let entry = by_ecosystem.entry(record.ecosystem.clone()).or_insert((0, 0));
            entry.0 = entry.0.saturating_add(record.recent_change_hits);
            entry.1 = entry.1.saturating_add(record.recent_change_misses);
        }

        let strength = self.config.empirical_bayes_strength;
        let shrinkage = self.config.empirical_bayes_shrinkage;
        by_ecosystem
            .into_iter()
            .map(|(ecosystem, (hits, misses))| {
                let total = hits + misses;
                let local_rate = (hits as f64 + 1.0) / (total as f64 + 2.0);
                let sample_weight = total as f64 / (total as f64 + strength);
                let blended = sample_weight * local_rate
                    + (1.0 - sample_weight) * global_rate;
                let rate = (1.0 - shrinkage) * blended
                    + shrinkage * global_rate;
                (
                    ecosystem,
                    (
                        (1.0 + strength * rate).max(1e-9),
                        (1.0 + strength * (1.0 - rate)).max(1e-9),
                    ),
                )
            })
            .collect()
    }

    fn change_probability(
        &self,
        record: &RepositorySignal,
        prior: (f64, f64),
    ) -> (f64, f64) {
        let alpha = prior.0 + record.recent_change_hits as f64;
        let beta = prior.1 + record.recent_change_misses as f64;
        let total = alpha + beta;
        let probability = alpha / total.max(1e-12);
        let variance =
            alpha * beta / (total * total * (total + 1.0)).max(1e-12);
        (clamp01(probability), variance.sqrt())
    }

    fn normalized_local_features(
        &self,
        record: &RepositorySignal,
        population: &[RepositorySignal],
    ) -> Vec<f64> {
        let raw = [
            record.commit_velocity,
            record.release_velocity,
            record.issue_velocity,
            record.contributor_velocity,
            record.maintainer_activity,
            record.security_signal,
            record.breakage_risk,
            record.dependency_importance,
            record.novelty,
            record.downstream_relevance,
        ];

        let columns: Vec<Vec<f64>> = (0..raw.len())
            .map(|index| {
                population
                    .iter()
                    .map(|candidate| {
                        [
                            candidate.commit_velocity,
                            candidate.release_velocity,
                            candidate.issue_velocity,
                            candidate.contributor_velocity,
                            candidate.maintainer_activity,
                            candidate.security_signal,
                            candidate.breakage_risk,
                            candidate.dependency_importance,
                            candidate.novelty,
                            candidate.downstream_relevance,
                        ][index]
                    })
                    .collect()
            })
            .collect();

        raw.iter()
            .enumerate()
            .map(|(index, value)| {
                let center = robust::median(&columns[index]);
                let scale = robust::mad(&columns[index], Some(center));
                stable_sigmoid((*value - center) / scale.max(1e-9))
            })
            .collect()
    }

    fn reliability(&self, record: &RepositorySignal) -> f64 {
        let base = clamp01(record.source_reliability);
        let decay = (-0.22 * record.failure_streak as f64).exp();
        clamp01((base * decay).max(0.05))
    }

    fn tail_risk(&self, record: &RepositorySignal) -> f64 {
        let mut impacts: Vec<f64> = record
            .impact_history
            .iter()
            .map(|value| clamp01(*value / 10.0))
            .collect();

        let cvar = if impacts.is_empty() {
            0.0
        } else {
            impacts.sort_by(f64::total_cmp);
            let start = ((impacts.len() as f64 * self.config.cvar_quantile)
                .floor() as usize)
                .min(impacts.len() - 1);
            impacts[start..].iter().sum::<f64>() / (impacts.len() - start) as f64
        };

        let security = clamp01(record.security_signal / 10.0);
        let breakage = clamp01(record.breakage_risk / 10.0);
        let failure = 1.0 - (-0.28 * record.failure_streak as f64).exp();
        clamp01(
            0.46 * cvar
                + 0.24 * security
                + 0.18 * breakage
                + 0.12 * failure,
        )
    }

    fn bayesian_surprise(
        &self,
        record: &RepositorySignal,
        predicted: f64,
    ) -> f64 {
        let empirical = if !record.change_history.is_empty() {
            let window = record.change_history.len().min(12);
            let tail = &record.change_history[record.change_history.len() - window..];
            (tail.iter().map(|value| (*value != 0) as u32).sum::<u32>() as f64 + 0.5)
                / (tail.len() as f64 + 1.0)
        } else {
            let total = record.recent_change_hits + record.recent_change_misses;
            (record.recent_change_hits as f64 + 0.5) / (total as f64 + 1.0)
        };
        clamp01(1.0 - (-3.4 * bandit::bernoulli_kl(empirical, predicted)).exp())
    }

    fn graph_from_records(&self, records: &[RepositorySignal]) -> Graph {
        records
            .iter()
            .map(|record| (record.name.clone(), record.normalized_dependencies()))
            .collect()
    }

    fn graph_gallery(
        &self,
        records: &[RepositorySignal],
        change_seeds: &BTreeMap<String, f64>,
    ) -> BTreeMap<String, GalleryEvidence> {
        let graph = self.graph_from_records(records);
        graph::centrality_consensus(&graph, Some(change_seeds))
            .into_iter()
            .map(|(name, (consensus, votes))| {
                let evidence = GalleryEvidence::new(
                    "graph",
                    votes
                        .into_iter()
                        .map(|(exhibit, score)| GalleryVote {
                            exhibit: exhibit.into(),
                            score,
                        })
                        .collect(),
                );
                debug_assert!((evidence.consensus - consensus).abs() <= 0.5);
                (name, evidence)
            })
            .collect()
    }

    fn robust_gallery(&self, local_features: &[f64]) -> GalleryEvidence {
        let huber = stable_sigmoid(robust::huber_location(local_features, 1.345, 16));
        let trimmed = stable_sigmoid(robust::trimmed_mean(local_features, 0.10));
        let outlier_fraction = robust::hampel_outlier_fraction(local_features, 3.0);
        let slope = clamp01(robust::theil_sen_slope(local_features).abs());

        GalleryEvidence::new(
            "robust-statistics",
            vec![
                GalleryVote {
                    exhibit: "huber".into(),
                    score: clamp01(huber),
                },
                GalleryVote {
                    exhibit: "trimmed-mean".into(),
                    score: clamp01(trimmed),
                },
                GalleryVote {
                    exhibit: "hampel-cleanliness".into(),
                    score: clamp01(1.0 - outlier_fraction),
                },
                GalleryVote {
                    exhibit: "theil-sen".into(),
                    score: slope,
                },
            ],
        )
    }

    fn change_gallery(&self, record: &RepositorySignal) -> GalleryEvidence {
        let votes = change::ensemble(&record.impact_history, &record.change_history)
            .into_iter()
            .map(|(exhibit, score)| GalleryVote {
                exhibit: exhibit.into(),
                score,
            })
            .collect();
        GalleryEvidence::new("change-detection", votes)
    }

    fn information_gallery(&self, record: &RepositorySignal) -> GalleryEvidence {
        let normalized: Vec<f64> = record
            .impact_history
            .iter()
            .map(|value| clamp01(*value / 10.0))
            .collect();
        let (_, votes) = information::distribution_shift(&normalized);
        GalleryEvidence::new(
            "information-distance",
            votes
                .into_iter()
                .map(|(exhibit, score)| GalleryVote {
                    exhibit: exhibit.into(),
                    score,
                })
                .collect(),
        )
    }

    fn exploration_gallery(
        &self,
        record: &RepositorySignal,
        total_observations: u32,
    ) -> GalleryEvidence {
        let normalized_history: Vec<f64> = record
            .impact_history
            .iter()
            .map(|value| clamp01(*value / 10.0))
            .collect();
        let variance = robust::winsorized_variance(&normalized_history, 3.5);
        let votes = bandit::exploration_votes(
            record.recent_change_hits,
            record.recent_change_misses,
            record.observations(),
            variance,
            total_observations,
        );

        GalleryEvidence::new(
            "online-learning",
            votes
                .into_iter()
                .map(|(exhibit, score)| GalleryVote {
                    exhibit: exhibit.into(),
                    score,
                })
                .collect(),
        )
    }

    fn sketches_gallery(
        &self,
        record: &RepositorySignal,
        peers: &[Vec<String>],
    ) -> GalleryEvidence {
        let dependencies = record.normalized_dependencies();
        let novelty = sketches::dependency_novelty(&dependencies, peers, 64);
        let average_exact_similarity = if peers.is_empty() {
            0.0
        } else {
            peers
                .iter()
                .map(|peer| sketches::exact_jaccard(&dependencies, peer))
                .sum::<f64>()
                / peers.len() as f64
        };
        GalleryEvidence::new(
            "streaming-sketch",
            vec![
                GalleryVote {
                    exhibit: "minhash-novelty".into(),
                    score: novelty,
                },
                GalleryVote {
                    exhibit: "exact-jaccard-novelty".into(),
                    score: clamp01(1.0 - average_exact_similarity),
                },
            ],
        )
    }

    fn reasons(&self, candidate: &Candidate) -> Vec<String> {
        let mut reasons = Vec::new();
        if candidate.change_probability >= 0.65 {
            reasons.push("likely-change".into());
        }
        if candidate.museum.change.consensus >= 0.55 {
            reasons.push("change-consensus".into());
        }
        if candidate.museum.information.consensus >= 0.45 {
            reasons.push("information-shift".into());
        }
        if candidate.graph_influence >= 0.55 {
            reasons.push("dependency-hub".into());
        }
        if candidate.structural_novelty >= 0.55 {
            reasons.push("structural-novelty".into());
        }
        if candidate.tail_risk >= 0.70 {
            reasons.push("tail-risk".into());
        }
        if candidate.museum.consensus >= 0.62 {
            reasons.push("museum-consensus".into());
        }
        if candidate.museum.disagreement >= 0.45 {
            reasons.push("algorithm-disagreement".into());
        }
        reasons
    }

    pub fn score(&self, records: &[RepositorySignal]) -> Vec<Candidate> {
        if records.is_empty() {
            return Vec::new();
        }

        let priors = self.empirical_bayes_priors(records);
        let total_observations = 1 + records.iter().map(RepositorySignal::observations).sum::<u32>();
        let mut preliminary = BTreeMap::new();

        for record in records {
            let prior = priors
                .get(&record.ecosystem)
                .copied()
                .unwrap_or((1.0, 1.0));
            let (probability, uncertainty) = self.change_probability(record, prior);
            let local_features = self.normalized_local_features(record, records);
            let local_signal = robust::bounded_robust_activity(&local_features);
            let surprise = self.bayesian_surprise(record, probability);
            preliminary.insert(
                record.name.clone(),
                (
                    probability,
                    uncertainty,
                    local_features,
                    local_signal,
                    surprise,
                ),
            );
        }

        let change_seeds: BTreeMap<String, f64> = records
            .iter()
            .map(|record| {
                let values = &preliminary[&record.name];
                (
                    record.name.clone(),
                    clamp01(
                        0.45 * values.0
                            + 0.35 * values.3
                            + 0.20 * values.4,
                    ),
                )
            })
            .collect();
        let graph_galleries = self.graph_gallery(records, &change_seeds);

        let dependency_sets: BTreeMap<String, Vec<String>> = records
            .iter()
            .map(|record| (record.name.clone(), record.normalized_dependencies()))
            .collect();

        let mut scored = Vec::with_capacity(records.len());
        for record in records {
            let (probability, uncertainty, local_features, local_signal, surprise) =
                preliminary[&record.name].clone();

            let robust_gallery = self.robust_gallery(&local_features);
            let change_gallery = self.change_gallery(record);
            let information_gallery = self.information_gallery(record);
            let graph_gallery = graph_galleries
                .get(&record.name)
                .cloned()
                .unwrap_or_else(|| GalleryEvidence::new("graph", Vec::new()));
            let exploration_gallery =
                self.exploration_gallery(record, total_observations);
            let peers: Vec<Vec<String>> = records
                .iter()
                .filter(|peer| peer.name != record.name)
                .map(|peer| dependency_sets[&peer.name].clone())
                .collect();
            let sketches_gallery = self.sketches_gallery(record, &peers);

            let museum = MuseumEvidence::from_galleries(
                robust_gallery,
                change_gallery,
                information_gallery,
                graph_gallery,
                exploration_gallery,
                sketches_gallery,
            );

            let graph_influence = museum.graph.consensus;
            let structural_novelty = clamp01(
                0.55 * museum.sketches.consensus
                    + 0.25 * clamp01(record.novelty / 10.0)
                    + 0.20 * museum.information.consensus,
            );
            let tail_risk = self.tail_risk(record);
            let reliability = self.reliability(record);
            let exploration = museum.exploration.consensus;
            let freshness = 1.0 - (-record.freshness_hours.max(0.0) / 48.0).exp();
            let security = clamp01(record.security_signal / 10.0);
            let dependency = clamp01(record.dependency_importance / 10.0);
            let downstream = clamp01(record.downstream_relevance / 10.0);

            let base = (
                0.16 * probability
                    + 0.11 * local_signal
                    + 0.10 * graph_influence
                    + 0.08 * structural_novelty
                    + 0.08 * surprise
                    + 0.08 * museum.change.consensus
                    + 0.07 * museum.information.consensus
                    + 0.07 * exploration
                    + 0.06 * security
                    + 0.05 * dependency
                    + 0.04 * downstream
                    + 0.04 * freshness
                    + self.config.museum_weight * museum.consensus
            ) / (0.94 + self.config.museum_weight);

            let disagreement_discount =
                1.0 - self.config.museum_disagreement_penalty * museum.disagreement;
            let risk_adjusted = base
                * disagreement_discount
                * (1.0 - self.config.tail_risk_penalty * tail_risk)
                * (0.82 + 0.18 * reliability);

            let utility = risk_adjusted
                * (1.0 + 0.04 * uncertainty.min(1.0))
                * (1.0 + 0.05 / record.cost.max(1) as f64);

            let mut tags = record.tags.clone();
            tags.insert(record.ecosystem.clone());
            tags.extend(record.normalized_dependencies());

            let mut candidate = Candidate {
                name: record.name.clone(),
                ecosystem: record.ecosystem.clone(),
                cost: record.cost.max(1),
                change_probability: probability,
                uncertainty,
                local_signal,
                graph_influence,
                structural_novelty,
                tail_risk,
                reliability,
                exploration,
                risk_adjusted_utility: risk_adjusted,
                utility,
                museum,
                reasons: Vec::new(),
                tags,
            };
            candidate.reasons = self.reasons(&candidate);
            candidate.tags.extend(candidate.reasons.iter().cloned());
            scored.push(candidate);
        }

        scored.sort_by(|left, right| {
            right
                .utility
                .partial_cmp(&left.utility)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| left.name.cmp(&right.name))
        });
        scored
    }

    pub fn schedule(
        &self,
        records: &[RepositorySignal],
        budget: u32,
    ) -> Schedule {
        let candidates = self.score(records);
        let (selected_names, objective) = optimization::constrained_beam(
            &candidates,
            budget,
            self.config.beam_width,
            self.config.ecosystem_cap,
            self.config.coverage_bonus,
            self.config.redundancy_penalty,
        );

        let by_name: BTreeMap<String, Candidate> = candidates
            .into_iter()
            .map(|candidate| (candidate.name.clone(), candidate))
            .collect();
        let selected_set: BTreeSet<String> = selected_names.iter().cloned().collect();
        let selected: Vec<Candidate> = selected_names
            .iter()
            .filter_map(|name| by_name.get(name).cloned())
            .collect();
        let spent = selected.iter().map(|candidate| candidate.cost).sum();

        let items: Vec<Item> = by_name.values().map(Item::from).collect();
        let exact = optimization::exact_knapsack(&items, budget);
        let celf = optimization::celf_select(&items, budget);
        let pareto = optimization::epsilon_pareto(&items, 1e-6);

        let production_utility = selected
            .iter()
            .map(|candidate| candidate.utility)
            .sum::<f64>();
        let exact_utility = exact
            .iter()
            .filter_map(|name| by_name.get(name))
            .map(|candidate| candidate.utility)
            .sum::<f64>();
        let ratio = if exact_utility > 0.0 {
            (production_utility / exact_utility).min(1.0)
        } else {
            1.0
        };

        let mut audit = BTreeMap::new();
        audit.insert("production".into(), json!(selected_set));
        audit.insert("exact_knapsack".into(), json!(exact));
        audit.insert("celf".into(), json!(celf));
        audit.insert("pareto".into(), json!(pareto));
        audit.insert("base_utility_ratio".into(), json!(ratio));

        Schedule {
            selected,
            budget,
            spent,
            objective,
            audit,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn signal(name: &str, ecosystem: &str, cost: u32) -> RepositorySignal {
        RepositorySignal {
            name: name.into(),
            ecosystem: ecosystem.into(),
            cost,
            freshness_hours: 2.0,
            commit_velocity: 4.0,
            release_velocity: 2.0,
            issue_velocity: 3.0,
            contributor_velocity: 2.0,
            maintainer_activity: 5.0,
            security_signal: 3.0,
            breakage_risk: 2.0,
            dependency_importance: 5.0,
            novelty: 6.0,
            downstream_relevance: 4.0,
            recent_change_hits: 4,
            recent_change_misses: 3,
            observation_count: 16,
            failure_streak: 0,
            source_reliability: 0.95,
            change_history: vec![0, 0, 1, 0, 1, 1],
            impact_history: vec![1.0, 2.0, 3.0, 5.0, 7.0],
            dependencies: Vec::new(),
            tags: BTreeSet::new(),
        }
    }

    #[test]
    fn scheduler_scores_and_selects() {
        let mut a = signal("a", "kernel", 2);
        a.dependencies = vec!["hub".into()];
        let mut b = signal("b", "app", 1);
        b.recent_change_hits = 1;
        b.recent_change_misses = 9;
        let hub = signal("hub", "kernel", 2);

        let scheduler = SkopraedScheduler::default();
        let scores = scheduler.score(&[a.clone(), b.clone(), hub.clone()]);
        assert_eq!(scores.len(), 3);
        assert!(scores.iter().all(|candidate| {
            (0.0..=1.0).contains(&candidate.museum.consensus)
                && candidate.utility.is_finite()
        }));

        let schedule = scheduler.schedule(&[a, b, hub], 3);
        assert!(schedule.spent <= 3);
        assert!(!schedule.selected.is_empty());
        assert!(schedule.audit.contains_key("exact_knapsack"));
    }
}
