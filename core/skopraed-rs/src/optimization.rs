use crate::model::Candidate;
use std::collections::{BTreeMap, BTreeSet};
use std::cmp::Ordering;

#[derive(Debug, Clone, PartialEq)]
pub struct Item {
    pub name: String,
    pub cost: u32,
    pub utility: f64,
    pub novelty: f64,
    pub risk: f64,
    pub tags: BTreeSet<String>,
}

impl From<&Candidate> for Item {
    fn from(candidate: &Candidate) -> Self {
        Self {
            name: candidate.name.clone(),
            cost: candidate.cost,
            utility: candidate.utility,
            novelty: candidate.structural_novelty,
            risk: candidate.tail_risk,
            tags: candidate.tags.clone(),
        }
    }
}

pub fn exact_knapsack(items: &[Item], budget: u32) -> Vec<String> {
    if budget == 0 || items.is_empty() {
        return Vec::new();
    }
    let mut dp: Vec<(f64, Vec<String>)> = vec![(0.0, Vec::new()); budget as usize + 1];

    for item in items {
        assert!(item.cost > 0);
        if item.cost > budget {
            continue;
        }
        for capacity in (item.cost..=budget).rev() {
            let previous = &dp[(capacity - item.cost) as usize];
            let mut names = previous.1.clone();
            names.push(item.name.clone());
            names.sort();
            let candidate = (previous.0 + item.utility, names);

            let current = &dp[capacity as usize];
            if candidate.0 > current.0 + 1e-12
                || ((candidate.0 - current.0).abs() <= 1e-12 && candidate.1 < current.1)
            {
                dp[capacity as usize] = candidate;
            }
        }
    }

    dp.into_iter()
        .max_by(|left, right| {
            left.0
                .partial_cmp(&right.0)
                .unwrap_or(Ordering::Equal)
                .then_with(|| right.1.cmp(&left.1))
        })
        .map(|(_, names)| names)
        .unwrap_or_default()
}

fn covered_tags(selected: &BTreeSet<String>, by_name: &BTreeMap<String, &Item>) -> BTreeSet<String> {
    let mut covered = BTreeSet::new();
    for name in selected {
        if let Some(item) = by_name.get(name) {
            covered.extend(item.tags.iter().cloned());
        }
    }
    covered
}

pub fn celf_select(items: &[Item], budget: u32) -> Vec<String> {
    let by_name: BTreeMap<String, &Item> =
        items.iter().map(|item| (item.name.clone(), item)).collect();
    let mut selected = BTreeSet::new();
    let mut spent = 0u32;

    #[derive(Debug, Clone)]
    struct Cache {
        gain: f64,
        stamp: usize,
    }

    let marginal = |item: &Item, selected: &BTreeSet<String>| {
        let covered = covered_tags(selected, &by_name);
        let new_tags = item.tags.difference(&covered).count() as f64;
        new_tags + 0.50 * item.utility + 0.25 * item.novelty - 0.15 * item.risk
    };

    let mut cache: BTreeMap<String, Cache> = items
        .iter()
        .map(|item| {
            (
                item.name.clone(),
                Cache {
                    gain: marginal(item, &selected),
                    stamp: 0,
                },
            )
        })
        .collect();

    while !cache.is_empty() {
        let best_name = cache
            .iter()
            .max_by(|(left_name, left), (right_name, right)| {
                let left_cost = by_name[*left_name].cost.max(1) as f64;
                let right_cost = by_name[*right_name].cost.max(1) as f64;
                (left.gain / left_cost)
                    .partial_cmp(&(right.gain / right_cost))
                    .unwrap_or(Ordering::Equal)
                    .then_with(|| left.gain.partial_cmp(&right.gain).unwrap_or(Ordering::Equal))
                    .then_with(|| right_name.cmp(left_name))
            })
            .map(|(name, _)| name.clone())
            .expect("cache is non-empty");

        let stale = cache[&best_name].stamp != selected.len();
        if stale {
            let gain = marginal(by_name[&best_name], &selected);
            if let Some(entry) = cache.get_mut(&best_name) {
                entry.gain = gain;
                entry.stamp = selected.len();
            }
            continue;
        }

        let entry = cache.remove(&best_name).expect("selected cache entry");
        let item = by_name[&best_name];
        if spent + item.cost > budget {
            continue;
        }
        if entry.gain <= 0.0 {
            break;
        }
        selected.insert(best_name);
        spent += item.cost;
    }

    selected.into_iter().collect()
}

pub fn epsilon_pareto(
    items: &[Item],
    epsilon: f64,
) -> Vec<String> {
    let epsilon = epsilon.max(0.0);
    let dominates = |left: &Item, right: &Item| {
        let weak = left.utility + epsilon >= right.utility
            && left.novelty + epsilon >= right.novelty
            && left.risk <= right.risk + epsilon;
        let strict = left.utility > right.utility + epsilon
            || left.novelty > right.novelty + epsilon
            || left.risk + epsilon < right.risk;
        weak && strict
    };

    let mut frontier: Vec<String> = items
        .iter()
        .enumerate()
        .filter(|(index, item)| {
            !items
                .iter()
                .enumerate()
                .any(|(other_index, other)| other_index != *index && dominates(other, item))
        })
        .map(|(_, item)| item.name.clone())
        .collect();
    frontier.sort();
    frontier
}

pub fn portfolio_utility(
    selected: &[String],
    items: &[Item],
    coverage_bonus: f64,
    redundancy_penalty: f64,
) -> f64 {
    let by_name: BTreeMap<String, &Item> =
        items.iter().map(|item| (item.name.clone(), item)).collect();
    let mut total = 0.0;
    let mut tag_counts: BTreeMap<String, usize> = BTreeMap::new();

    for name in selected {
        let Some(item) = by_name.get(name) else {
            continue;
        };
        total += item.utility;
        for tag in &item.tags {
            *tag_counts.entry(tag.clone()).or_insert(0) += 1;
        }
    }

    let unique = tag_counts.len() as f64;
    let duplicates = tag_counts
        .values()
        .map(|count| count.saturating_sub(1) as f64)
        .sum::<f64>();
    total + coverage_bonus * unique - redundancy_penalty * duplicates
}

#[derive(Debug, Clone)]
struct BeamState {
    selected: Vec<String>,
    spent: u32,
    objective: f64,
    ecosystem_counts: BTreeMap<String, usize>,
}

pub fn constrained_beam(
    candidates: &[Candidate],
    budget: u32,
    beam_width: usize,
    ecosystem_cap: usize,
    coverage_bonus: f64,
    redundancy_penalty: f64,
) -> (Vec<String>, f64) {
    let items: Vec<Item> = candidates.iter().map(Item::from).collect();
    let by_name: BTreeMap<String, &Candidate> =
        candidates.iter().map(|candidate| (candidate.name.clone(), candidate)).collect();

    let mut beam = vec![BeamState {
        selected: Vec::new(),
        spent: 0,
        objective: 0.0,
        ecosystem_counts: BTreeMap::new(),
    }];

    let ordered: Vec<&Candidate> = {
        let mut values: Vec<&Candidate> = candidates.iter().collect();
        values.sort_by(|left, right| {
            (right.utility / right.cost.max(1) as f64)
                .partial_cmp(&(left.utility / left.cost.max(1) as f64))
                .unwrap_or(Ordering::Equal)
                .then_with(|| left.name.cmp(&right.name))
        });
        values
    };

    for candidate in ordered {
        let mut next = beam.clone();
        for state in &beam {
            if state.spent + candidate.cost > budget {
                continue;
            }
            let ecosystem_count = state
                .ecosystem_counts
                .get(&candidate.ecosystem)
                .copied()
                .unwrap_or(0);
            if ecosystem_count >= ecosystem_cap {
                continue;
            }

            let mut selected = state.selected.clone();
            selected.push(candidate.name.clone());
            selected.sort();

            let mut ecosystem_counts = state.ecosystem_counts.clone();
            *ecosystem_counts
                .entry(candidate.ecosystem.clone())
                .or_insert(0) += 1;

            let objective = portfolio_utility(
                &selected,
                &items,
                coverage_bonus,
                redundancy_penalty,
            );

            next.push(BeamState {
                selected,
                spent: state.spent + candidate.cost,
                objective,
                ecosystem_counts,
            });
        }

        next.sort_by(|left, right| {
            right
                .objective
                .partial_cmp(&left.objective)
                .unwrap_or(Ordering::Equal)
                .then_with(|| left.spent.cmp(&right.spent))
                .then_with(|| left.selected.cmp(&right.selected))
        });
        next.dedup_by(|left, right| left.selected == right.selected);
        next.truncate(beam_width.max(8));
        beam = next;
    }

    let best = beam
        .into_iter()
        .max_by(|left, right| {
            left.objective
                .partial_cmp(&right.objective)
                .unwrap_or(Ordering::Equal)
                .then_with(|| right.spent.cmp(&left.spent))
                .then_with(|| right.selected.cmp(&left.selected))
        })
        .unwrap_or(BeamState {
            selected: Vec::new(),
            spent: 0,
            objective: 0.0,
            ecosystem_counts: BTreeMap::new(),
        });

    // Defensive: every returned name must exist.
    debug_assert!(best.selected.iter().all(|name| by_name.contains_key(name)));
    (best.selected, best.objective)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(name: &str, cost: u32, utility: f64) -> Item {
        Item {
            name: name.into(),
            cost,
            utility,
            novelty: utility / 10.0,
            risk: 0.1,
            tags: BTreeSet::from([name.into()]),
        }
    }

    #[test]
    fn exact_knapsack_finds_optimum() {
        let items = vec![item("a", 3, 5.0), item("b", 2, 3.0), item("c", 2, 4.0)];
        assert_eq!(exact_knapsack(&items, 4), vec!["b".to_string(), "c".to_string()]);
    }

    #[test]
    fn pareto_removes_dominated() {
        let mut a = item("a", 1, 0.8);
        a.novelty = 0.7;
        a.risk = 0.4;
        let mut b = item("b", 1, 0.7);
        b.novelty = 0.6;
        b.risk = 0.5;
        let mut c = item("c", 1, 0.6);
        c.novelty = 0.9;
        c.risk = 0.2;
        let frontier = epsilon_pareto(&[a, b, c], 1e-6);
        assert!(!frontier.contains(&"b".to_string()));
        assert!(frontier.contains(&"a".to_string()));
        assert!(frontier.contains(&"c".to_string()));
    }
}
