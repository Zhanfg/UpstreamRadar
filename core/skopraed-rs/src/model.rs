use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

fn default_cost() -> u32 {
    1
}

fn default_reliability() -> f64 {
    1.0
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RepositorySignal {
    pub name: String,
    #[serde(default)]
    pub ecosystem: String,
    #[serde(default = "default_cost")]
    pub cost: u32,
    #[serde(default)]
    pub freshness_hours: f64,

    #[serde(default)]
    pub commit_velocity: f64,
    #[serde(default)]
    pub release_velocity: f64,
    #[serde(default)]
    pub issue_velocity: f64,
    #[serde(default)]
    pub contributor_velocity: f64,
    #[serde(default)]
    pub maintainer_activity: f64,

    #[serde(default)]
    pub security_signal: f64,
    #[serde(default)]
    pub breakage_risk: f64,
    #[serde(default)]
    pub dependency_importance: f64,
    #[serde(default)]
    pub novelty: f64,
    #[serde(default)]
    pub downstream_relevance: f64,

    #[serde(default)]
    pub recent_change_hits: u32,
    #[serde(default)]
    pub recent_change_misses: u32,
    #[serde(default)]
    pub observation_count: u32,
    #[serde(default)]
    pub failure_streak: u32,

    #[serde(default = "default_reliability")]
    pub source_reliability: f64,

    #[serde(default)]
    pub change_history: Vec<u8>,
    #[serde(default)]
    pub impact_history: Vec<f64>,
    #[serde(default)]
    pub dependencies: Vec<String>,
    #[serde(default)]
    pub tags: BTreeSet<String>,
}

impl RepositorySignal {
    pub fn normalized_dependencies(&self) -> Vec<String> {
        let mut seen = BTreeSet::new();
        self.dependencies
            .iter()
            .filter_map(|dependency| {
                let value = dependency.trim();
                if value.is_empty() || value == self.name {
                    return None;
                }
                if seen.insert(value.to_owned()) {
                    Some(value.to_owned())
                } else {
                    None
                }
            })
            .collect()
    }

    pub fn observations(&self) -> u32 {
        self.observation_count
            .max(self.recent_change_hits + self.recent_change_misses)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GalleryVote {
    pub exhibit: String,
    pub score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GalleryEvidence {
    pub family: String,
    pub consensus: f64,
    pub disagreement: f64,
    pub votes: Vec<GalleryVote>,
}

impl GalleryEvidence {
    pub fn new(family: impl Into<String>, votes: Vec<GalleryVote>) -> Self {
        if votes.is_empty() {
            return Self {
                family: family.into(),
                consensus: 0.0,
                disagreement: 0.0,
                votes,
            };
        }

        let mean = votes.iter().map(|vote| vote.score).sum::<f64>() / votes.len() as f64;
        let variance = votes
            .iter()
            .map(|vote| {
                let delta = vote.score - mean;
                delta * delta
            })
            .sum::<f64>()
            / votes.len() as f64;
        let disagreement = (variance.sqrt() * 2.0).clamp(0.0, 1.0);
        let consensus = (mean * (1.0 - 0.22 * disagreement)).clamp(0.0, 1.0);

        Self {
            family: family.into(),
            consensus,
            disagreement,
            votes,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MuseumEvidence {
    pub robust: GalleryEvidence,
    pub change: GalleryEvidence,
    pub information: GalleryEvidence,
    pub graph: GalleryEvidence,
    pub exploration: GalleryEvidence,
    pub sketches: GalleryEvidence,

    pub consensus: f64,
    pub disagreement: f64,
}

impl MuseumEvidence {
    pub fn from_galleries(
        robust: GalleryEvidence,
        change: GalleryEvidence,
        information: GalleryEvidence,
        graph: GalleryEvidence,
        exploration: GalleryEvidence,
        sketches: GalleryEvidence,
    ) -> Self {
        let galleries = [&robust, &change, &information, &graph, &exploration, &sketches];
        let mean = galleries.iter().map(|gallery| gallery.consensus).sum::<f64>()
            / galleries.len() as f64;
        let disagreement = galleries
            .iter()
            .map(|gallery| {
                let delta = gallery.consensus - mean;
                delta * delta
            })
            .sum::<f64>()
            / galleries.len() as f64;
        let disagreement = (disagreement.sqrt() * 2.0).clamp(0.0, 1.0);
        let consensus = (mean * (1.0 - 0.24 * disagreement)).clamp(0.0, 1.0);

        Self {
            robust,
            change,
            information,
            graph,
            exploration,
            sketches,
            consensus,
            disagreement,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Candidate {
    pub name: String,
    pub ecosystem: String,
    pub cost: u32,

    pub change_probability: f64,
    pub uncertainty: f64,
    pub local_signal: f64,
    pub graph_influence: f64,
    pub structural_novelty: f64,
    pub tail_risk: f64,
    pub reliability: f64,
    pub exploration: f64,
    pub risk_adjusted_utility: f64,
    pub utility: f64,

    pub museum: MuseumEvidence,
    pub reasons: Vec<String>,
    pub tags: BTreeSet<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Schedule {
    pub selected: Vec<Candidate>,
    pub budget: u32,
    pub spent: u32,
    pub objective: f64,
    pub audit: BTreeMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SchedulerConfig {
    pub empirical_bayes_strength: f64,
    pub empirical_bayes_shrinkage: f64,
    pub pagerank_damping: f64,
    pub graph_steps: usize,
    pub cvar_quantile: f64,
    pub tail_risk_penalty: f64,
    pub museum_weight: f64,
    pub museum_disagreement_penalty: f64,
    pub ecosystem_cap: usize,
    pub beam_width: usize,
    pub coverage_bonus: f64,
    pub redundancy_penalty: f64,
}

impl Default for SchedulerConfig {
    fn default() -> Self {
        Self {
            empirical_bayes_strength: 4.0,
            empirical_bayes_shrinkage: 0.35,
            pagerank_damping: 0.84,
            graph_steps: 48,
            cvar_quantile: 0.75,
            tail_risk_penalty: 0.11,
            museum_weight: 0.12,
            museum_disagreement_penalty: 0.08,
            ecosystem_cap: 3,
            beam_width: 128,
            coverage_bonus: 0.08,
            redundancy_penalty: 0.10,
        }
    }
}

impl SchedulerConfig {
    pub fn validate(&self) -> Result<(), String> {
        if self.empirical_bayes_strength <= 0.0 {
            return Err("empirical_bayes_strength must be positive".into());
        }
        if !(0.0..=1.0).contains(&self.empirical_bayes_shrinkage) {
            return Err("empirical_bayes_shrinkage must be in [0,1]".into());
        }
        if !(0.0..1.0).contains(&self.pagerank_damping) {
            return Err("pagerank_damping must be in [0,1)".into());
        }
        if !(0.5..1.0).contains(&self.cvar_quantile) {
            return Err("cvar_quantile must be in [0.5,1)".into());
        }
        if self.ecosystem_cap == 0 {
            return Err("ecosystem_cap must be positive".into());
        }
        if self.beam_width < 8 {
            return Err("beam_width must be >= 8".into());
        }
        Ok(())
    }
}
