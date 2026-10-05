use harmony_museum::{
    graph::{self, Graph},
    information,
    optimization::{self, Item},
    sketches,
    HarmonyScheduler, RepositorySignal,
};
use std::collections::{BTreeMap, BTreeSet};

fn repository(name: &str, ecosystem: &str, cost: u32) -> RepositorySignal {
    RepositorySignal {
        name: name.into(),
        ecosystem: ecosystem.into(),
        cost,
        freshness_hours: 4.0,
        commit_velocity: 5.0,
        release_velocity: 2.0,
        issue_velocity: 3.0,
        contributor_velocity: 2.0,
        maintainer_activity: 6.0,
        security_signal: 4.0,
        breakage_risk: 3.0,
        dependency_importance: 6.0,
        novelty: 6.0,
        downstream_relevance: 5.0,
        recent_change_hits: 4,
        recent_change_misses: 4,
        observation_count: 24,
        failure_streak: 0,
        source_reliability: 0.95,
        change_history: vec![0, 0, 0, 1, 0, 1, 1, 1],
        impact_history: vec![1.0, 1.0, 2.0, 2.0, 4.0, 6.0, 7.0, 8.0],
        dependencies: Vec::new(),
        tags: BTreeSet::new(),
    }
}

#[test]
fn end_to_end_schedule_is_deterministic() {
    let mut kernel = repository("kernel", "linux", 3);
    kernel.dependencies = vec!["toolchain".into()];
    kernel.security_signal = 8.0;
    kernel.dependency_importance = 9.0;

    let mut toolchain = repository("toolchain", "build", 2);
    toolchain.dependencies = vec!["runtime".into()];
    toolchain.recent_change_hits = 7;
    toolchain.recent_change_misses = 2;

    let mut runtime = repository("runtime", "language", 2);
    runtime.recent_change_hits = 2;
    runtime.recent_change_misses = 7;

    let app = repository("app", "android", 1);
    let records = vec![kernel, toolchain, runtime, app];

    let scheduler = HarmonyScheduler::default();
    let first = scheduler.schedule(&records, 5);
    let second = scheduler.schedule(&records, 5);

    assert_eq!(first, second);
    assert!(first.spent <= 5);
    assert!(!first.selected.is_empty());
    assert!(first.audit.contains_key("pareto"));
    assert!(first
        .selected
        .iter()
        .all(|candidate| candidate.museum.consensus.is_finite()));
}

#[test]
fn graph_gallery_distinguishes_structure() {
    let graph: Graph = BTreeMap::from([
        ("hub".into(), Vec::new()),
        ("a".into(), vec!["hub".into()]),
        ("b".into(), vec!["hub".into()]),
        ("c".into(), vec!["hub".into()]),
        ("chain".into(), vec!["a".into()]),
    ]);

    let consensus = graph::centrality_consensus(&graph, None);
    assert!(consensus["hub"].0 > 0.0);
    assert!(consensus.values().all(|(score, _)| (0.0..=1.0).contains(score)));

    let components = graph::tarjan_scc(&graph);
    assert_eq!(components.len(), 5);
}

#[test]
fn information_gallery_handles_mismatched_sample_sizes() {
    let older = [0.0, 0.1, 0.2, 0.1];
    let recent = [0.7, 0.8, 0.9, 1.0, 0.85, 0.95];
    assert!(information::wasserstein_1d(&older, &recent) > 0.5);
    assert!(information::maximum_mean_discrepancy(&older, &recent, None) > 0.3);
}

#[test]
fn sketches_have_expected_error_direction() {
    let exact_a = vec!["a".into(), "b".into(), "c".into(), "d".into()];
    let exact_b = vec!["a".into(), "b".into(), "x".into(), "y".into()];
    let exact = sketches::exact_jaccard(&exact_a, &exact_b);

    let signature_a = sketches::minhash_signature(&exact_a, 256);
    let signature_b = sketches::minhash_signature(&exact_b, 256);
    let approximate = sketches::minhash_similarity(&signature_a, &signature_b);
    assert!((exact - approximate).abs() < 0.20);
}

#[test]
fn optimization_oracles_are_consistent_on_simple_case() {
    let items = vec![
        Item {
            name: "a".into(),
            cost: 3,
            utility: 5.0,
            novelty: 0.5,
            risk: 0.2,
            tags: BTreeSet::from(["kernel".into()]),
        },
        Item {
            name: "b".into(),
            cost: 2,
            utility: 3.0,
            novelty: 0.8,
            risk: 0.1,
            tags: BTreeSet::from(["network".into()]),
        },
        Item {
            name: "c".into(),
            cost: 2,
            utility: 4.0,
            novelty: 0.7,
            risk: 0.15,
            tags: BTreeSet::from(["security".into()]),
        },
    ];

    assert_eq!(
        optimization::exact_knapsack(&items, 4),
        vec!["b".to_string(), "c".to_string()]
    );

    let frontier = optimization::epsilon_pareto(&items, 1e-6);
    assert!(frontier.contains(&"a".to_string()));
    assert!(frontier.contains(&"c".to_string()));
}
