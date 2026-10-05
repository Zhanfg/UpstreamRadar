use crate::clamp01;
use std::cmp::Reverse;
use std::collections::{BTreeMap, BTreeSet, BinaryHeap, VecDeque};

pub type Graph = BTreeMap<String, Vec<String>>;

fn nodes(graph: &Graph) -> Vec<String> {
    let mut out = BTreeSet::new();
    for (source, targets) in graph {
        out.insert(source.clone());
        for target in targets {
            out.insert(target.clone());
        }
    }
    out.into_iter().collect()
}

fn normalized_targets(graph: &Graph, source: &str, known: &BTreeSet<String>) -> Vec<String> {
    let mut seen = BTreeSet::new();
    graph
        .get(source)
        .into_iter()
        .flatten()
        .filter_map(|target| {
            if target == source || !known.contains(target) {
                return None;
            }
            if seen.insert(target.clone()) {
                Some(target.clone())
            } else {
                None
            }
        })
        .collect()
}

pub fn pagerank(
    graph: &Graph,
    damping: f64,
    steps: usize,
    seeds: Option<&BTreeMap<String, f64>>,
) -> BTreeMap<String, f64> {
    let vertices = nodes(graph);
    if vertices.is_empty() {
        return BTreeMap::new();
    }
    let known: BTreeSet<String> = vertices.iter().cloned().collect();

    let mut raw = BTreeMap::new();
    for vertex in &vertices {
        let value = seeds
            .and_then(|map| map.get(vertex))
            .copied()
            .unwrap_or(1.0)
            .max(1e-12);
        raw.insert(vertex.clone(), value);
    }
    let total = raw.values().sum::<f64>().max(1e-12);
    let teleport: BTreeMap<String, f64> =
        raw.into_iter().map(|(key, value)| (key, value / total)).collect();
    let mut rank = teleport.clone();
    let damping = damping.clamp(0.0, 0.999_999);

    for _ in 0..steps.max(1) {
        let mut next: BTreeMap<String, f64> = vertices
            .iter()
            .map(|vertex| {
                (
                    vertex.clone(),
                    (1.0 - damping) * teleport.get(vertex).copied().unwrap_or(0.0),
                )
            })
            .collect();

        let mut dangling = 0.0;
        for source in &vertices {
            let targets = normalized_targets(graph, source, &known);
            let source_rank = rank.get(source).copied().unwrap_or(0.0);
            if targets.is_empty() {
                dangling += source_rank;
                continue;
            }
            let share = damping * source_rank / targets.len() as f64;
            for target in targets {
                *next.entry(target).or_default() += share;
            }
        }

        if dangling > 0.0 {
            for vertex in &vertices {
                let teleport_weight = teleport.get(vertex).copied().unwrap_or(0.0);
                *next.entry(vertex.clone()).or_default() +=
                    damping * dangling * teleport_weight;
            }
        }
        rank = next;
    }

    let scale = rank.values().sum::<f64>().max(1e-12);
    rank.into_iter().map(|(key, value)| (key, value / scale)).collect()
}

pub fn hits(
    graph: &Graph,
    steps: usize,
) -> (BTreeMap<String, f64>, BTreeMap<String, f64>) {
    let vertices = nodes(graph);
    if vertices.is_empty() {
        return (BTreeMap::new(), BTreeMap::new());
    }
    let known: BTreeSet<String> = vertices.iter().cloned().collect();
    let mut incoming: BTreeMap<String, Vec<String>> =
        vertices.iter().map(|vertex| (vertex.clone(), Vec::new())).collect();
    let mut outgoing = BTreeMap::new();

    for source in &vertices {
        let targets = normalized_targets(graph, source, &known);
        for target in &targets {
            incoming.entry(target.clone()).or_default().push(source.clone());
        }
        outgoing.insert(source.clone(), targets);
    }

    let mut hubs: BTreeMap<String, f64> =
        vertices.iter().map(|vertex| (vertex.clone(), 1.0)).collect();
    let mut authorities = hubs.clone();

    for _ in 0..steps.max(1) {
        let mut next_authorities = BTreeMap::new();
        for vertex in &vertices {
            let value = incoming
                .get(vertex)
                .into_iter()
                .flatten()
                .map(|source| hubs.get(source).copied().unwrap_or(0.0))
                .sum::<f64>();
            next_authorities.insert(vertex.clone(), value);
        }
        let norm = next_authorities
            .values()
            .map(|value| value * value)
            .sum::<f64>()
            .sqrt()
            .max(1e-12);
        for value in next_authorities.values_mut() {
            *value /= norm;
        }

        let mut next_hubs = BTreeMap::new();
        for vertex in &vertices {
            let value = outgoing
                .get(vertex)
                .into_iter()
                .flatten()
                .map(|target| next_authorities.get(target).copied().unwrap_or(0.0))
                .sum::<f64>();
            next_hubs.insert(vertex.clone(), value);
        }
        let norm = next_hubs
            .values()
            .map(|value| value * value)
            .sum::<f64>()
            .sqrt()
            .max(1e-12);
        for value in next_hubs.values_mut() {
            *value /= norm;
        }
        hubs = next_hubs;
        authorities = next_authorities;
    }

    (hubs, authorities)
}

pub fn katz(
    graph: &Graph,
    alpha: Option<f64>,
    beta: f64,
    steps: usize,
) -> BTreeMap<String, f64> {
    let vertices = nodes(graph);
    if vertices.is_empty() {
        return BTreeMap::new();
    }
    let known: BTreeSet<String> = vertices.iter().cloned().collect();

    let mut incoming: BTreeMap<String, Vec<String>> =
        vertices.iter().map(|vertex| (vertex.clone(), Vec::new())).collect();
    let mut maximum_degree = 1usize;
    for source in &vertices {
        let targets = normalized_targets(graph, source, &known);
        maximum_degree = maximum_degree.max(targets.len());
        for target in targets {
            incoming.entry(target).or_default().push(source.clone());
        }
    }

    let attenuation = alpha.unwrap_or(0.85 / maximum_degree as f64);
    let mut scores: BTreeMap<String, f64> =
        vertices.iter().map(|vertex| (vertex.clone(), 1.0)).collect();

    for _ in 0..steps.max(1) {
        let mut next = BTreeMap::new();
        for vertex in &vertices {
            let incoming_score = incoming
                .get(vertex)
                .into_iter()
                .flatten()
                .map(|source| scores.get(source).copied().unwrap_or(0.0))
                .sum::<f64>();
            next.insert(vertex.clone(), beta + attenuation * incoming_score);
        }
        let scale = next.values().copied().fold(0.0_f64, f64::max).max(1e-12);
        for value in next.values_mut() {
            *value /= scale;
        }
        scores = next;
    }
    scores
}

pub fn tarjan_scc(graph: &Graph) -> Vec<Vec<String>> {
    struct Context<'a> {
        graph: &'a Graph,
        known: BTreeSet<String>,
        index: usize,
        stack: Vec<String>,
        on_stack: BTreeSet<String>,
        indices: BTreeMap<String, usize>,
        lowlink: BTreeMap<String, usize>,
        components: Vec<Vec<String>>,
    }

    fn visit(node: &str, context: &mut Context<'_>) {
        let index = context.index;
        context.index += 1;
        context.indices.insert(node.to_owned(), index);
        context.lowlink.insert(node.to_owned(), index);
        context.stack.push(node.to_owned());
        context.on_stack.insert(node.to_owned());

        let targets = normalized_targets(context.graph, node, &context.known);
        for target in targets {
            if !context.indices.contains_key(&target) {
                visit(&target, context);
                let low_target = context.lowlink[&target];
                let current = context.lowlink[node];
                context
                    .lowlink
                    .insert(node.to_owned(), current.min(low_target));
            } else if context.on_stack.contains(&target) {
                let target_index = context.indices[&target];
                let current = context.lowlink[node];
                context
                    .lowlink
                    .insert(node.to_owned(), current.min(target_index));
            }
        }

        if context.lowlink[node] == context.indices[node] {
            let mut component = Vec::new();
            while let Some(member) = context.stack.pop() {
                context.on_stack.remove(&member);
                component.push(member.clone());
                if member == node {
                    break;
                }
            }
            component.sort();
            context.components.push(component);
        }
    }

    let vertices = nodes(graph);
    let mut context = Context {
        graph,
        known: vertices.iter().cloned().collect(),
        index: 0,
        stack: Vec::new(),
        on_stack: BTreeSet::new(),
        indices: BTreeMap::new(),
        lowlink: BTreeMap::new(),
        components: Vec::new(),
    };

    for vertex in vertices {
        if !context.indices.contains_key(&vertex) {
            visit(&vertex, &mut context);
        }
    }
    context
        .components
        .sort_by(|left, right| left.first().cmp(&right.first()).then(left.len().cmp(&right.len())));
    context.components
}

pub fn brandes_betweenness(graph: &Graph) -> BTreeMap<String, f64> {
    let vertices = nodes(graph);
    let known: BTreeSet<String> = vertices.iter().cloned().collect();
    let mut score: BTreeMap<String, f64> =
        vertices.iter().map(|vertex| (vertex.clone(), 0.0)).collect();

    for source in &vertices {
        let mut stack = Vec::new();
        let mut predecessors: BTreeMap<String, Vec<String>> =
            vertices.iter().map(|vertex| (vertex.clone(), Vec::new())).collect();
        let mut sigma: BTreeMap<String, f64> =
            vertices.iter().map(|vertex| (vertex.clone(), 0.0)).collect();
        sigma.insert(source.clone(), 1.0);
        let mut distance: BTreeMap<String, i64> =
            vertices.iter().map(|vertex| (vertex.clone(), -1)).collect();
        distance.insert(source.clone(), 0);

        let mut queue = VecDeque::from([source.clone()]);
        while let Some(vertex) = queue.pop_front() {
            stack.push(vertex.clone());
            let vertex_distance = distance[&vertex];
            for target in normalized_targets(graph, &vertex, &known) {
                if distance[&target] < 0 {
                    queue.push_back(target.clone());
                    distance.insert(target.clone(), vertex_distance + 1);
                }
                if distance[&target] == vertex_distance + 1 {
                    let source_sigma = sigma[&vertex];
                    *sigma.entry(target.clone()).or_default() += source_sigma;
                    predecessors.entry(target).or_default().push(vertex.clone());
                }
            }
        }

        let mut dependency: BTreeMap<String, f64> =
            vertices.iter().map(|vertex| (vertex.clone(), 0.0)).collect();
        while let Some(target) = stack.pop() {
            let target_sigma = sigma[&target];
            if target_sigma > 0.0 {
                let coefficient = (1.0 + dependency[&target]) / target_sigma;
                for predecessor in &predecessors[&target] {
                    let contribution = sigma[predecessor] * coefficient;
                    *dependency.entry(predecessor.clone()).or_default() += contribution;
                }
            }
            if &target != source {
                *score.entry(target.clone()).or_default() += dependency[&target];
            }
        }
    }

    let maximum = score.values().copied().fold(0.0_f64, f64::max).max(1e-12);
    score
        .into_iter()
        .map(|(key, value)| (key, value / maximum))
        .collect()
}

pub fn k_core_numbers(graph: &Graph) -> BTreeMap<String, f64> {
    let vertices = nodes(graph);
    let mut adjacency: BTreeMap<String, BTreeSet<String>> =
        vertices.iter().map(|vertex| (vertex.clone(), BTreeSet::new())).collect();

    for source in &vertices {
        for target in graph.get(source).into_iter().flatten() {
            if target == source || !adjacency.contains_key(target) {
                continue;
            }
            adjacency.entry(source.clone()).or_default().insert(target.clone());
            adjacency.entry(target.clone()).or_default().insert(source.clone());
        }
    }

    let mut degree: BTreeMap<String, usize> = adjacency
        .iter()
        .map(|(vertex, neighbors)| (vertex.clone(), neighbors.len()))
        .collect();
    let mut heap = BinaryHeap::new();
    for (vertex, value) in &degree {
        heap.push(Reverse((*value, vertex.clone())));
    }

    let mut removed = BTreeSet::new();
    let mut core = BTreeMap::new();
    let mut degeneracy = 0usize;
    while let Some(Reverse((current_degree, vertex))) = heap.pop() {
        if removed.contains(&vertex) || degree[&vertex] != current_degree {
            continue;
        }
        removed.insert(vertex.clone());
        degeneracy = degeneracy.max(current_degree);
        core.insert(vertex.clone(), degeneracy);

        for neighbor in adjacency.get(&vertex).into_iter().flatten() {
            if removed.contains(neighbor) {
                continue;
            }
            if let Some(value) = degree.get_mut(neighbor) {
                *value = value.saturating_sub(1);
                heap.push(Reverse((*value, neighbor.clone())));
            }
        }
    }

    let maximum = core.values().copied().max().unwrap_or(1).max(1) as f64;
    vertices
        .into_iter()
        .map(|vertex| {
            let value = core.get(&vertex).copied().unwrap_or(0) as f64 / maximum;
            (vertex, value)
        })
        .collect()
}

pub fn centrality_consensus(
    graph: &Graph,
    seeds: Option<&BTreeMap<String, f64>>,
) -> BTreeMap<String, (f64, Vec<(&'static str, f64)>)> {
    let pr = pagerank(graph, 0.85, 48, seeds);
    let (hubs, authorities) = hits(graph, 32);
    let kz = katz(graph, None, 1.0, 40);
    let between = brandes_betweenness(graph);
    let core = k_core_numbers(graph);
    let components = tarjan_scc(graph);

    let cyclic: BTreeSet<String> = components
        .iter()
        .filter(|component| component.len() > 1)
        .flat_map(|component| component.iter().cloned())
        .collect();

    fn normalize(map: &BTreeMap<String, f64>, key: &str) -> f64 {
        let maximum = map.values().copied().fold(0.0_f64, f64::max).max(1e-12);
        map.get(key).copied().unwrap_or(0.0) / maximum
    }

    let mut out = BTreeMap::new();
    for vertex in nodes(graph) {
        let votes = vec![
            ("pagerank", normalize(&pr, &vertex)),
            ("hits-hub", normalize(&hubs, &vertex)),
            ("hits-authority", normalize(&authorities, &vertex)),
            ("katz", kz.get(&vertex).copied().unwrap_or(0.0)),
            ("brandes", between.get(&vertex).copied().unwrap_or(0.0)),
            ("k-core", core.get(&vertex).copied().unwrap_or(0.0)),
            ("tarjan-cycle", if cyclic.contains(&vertex) { 1.0 } else { 0.0 }),
        ];
        let mean = votes.iter().map(|(_, value)| *value).sum::<f64>() / votes.len() as f64;
        let maximum = votes.iter().map(|(_, value)| *value).fold(0.0_f64, f64::max);
        let minimum = votes.iter().map(|(_, value)| *value).fold(1.0_f64, f64::min);
        let spread = maximum - minimum;
        out.insert(vertex, (clamp01(mean * (1.0 - 0.16 * spread)), votes));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Graph {
        BTreeMap::from([
            ("a".into(), vec!["b".into()]),
            ("b".into(), vec!["c".into(), "hub".into()]),
            ("c".into(), vec!["a".into(), "hub".into()]),
            ("leaf".into(), vec!["hub".into()]),
            ("hub".into(), vec![]),
        ])
    }

    #[test]
    fn tarjan_finds_cycle() {
        let components = tarjan_scc(&sample());
        assert!(components.contains(&vec!["a".into(), "b".into(), "c".into()]));
    }

    #[test]
    fn consensus_is_bounded() {
        for (_, (score, _)) in centrality_consensus(&sample(), None) {
            assert!((0.0..=1.0).contains(&score));
        }
    }

    #[test]
    fn pagerank_is_probability_distribution() {
        let rank = pagerank(&sample(), 0.85, 64, None);
        assert!((rank.values().sum::<f64>() - 1.0).abs() < 1e-9);
    }
}
