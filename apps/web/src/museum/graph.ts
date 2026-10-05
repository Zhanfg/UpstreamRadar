import type {
  CentralityBundle,
  GraphEdge,
  GraphModel,
} from "./types.js";
import { clamp01 } from "./statistics.js";

type Adjacency = Map<string, string[]>;

const nodesOf = (model: GraphModel): string[] =>
  [...new Set(model.nodes.map((node) => node.id))].sort();

const adjacencyOf = (model: GraphModel): Adjacency => {
  const nodes = new Set(nodesOf(model));
  const adjacency = new Map<string, Set<string>>();
  for (const node of nodes) adjacency.set(node, new Set());
  for (const edge of model.edges) {
    if (
      edge.source === edge.target ||
      !nodes.has(edge.source) ||
      !nodes.has(edge.target)
    ) {
      continue;
    }
    adjacency.get(edge.source)!.add(edge.target);
  }
  return new Map(
    [...adjacency].map(([node, targets]) => [
      node,
      [...targets].sort(),
    ]),
  );
};

const incomingOf = (adjacency: Adjacency): Adjacency => {
  const incoming = new Map<string, string[]>();
  for (const node of adjacency.keys()) incoming.set(node, []);
  for (const [source, targets] of adjacency) {
    for (const target of targets) incoming.get(target)!.push(source);
  }
  for (const values of incoming.values()) values.sort();
  return incoming;
};

export function pageRank(
  model: GraphModel,
  {
    damping = 0.85,
    steps = 48,
    seeds = new Map<string, number>(),
  }: {
    damping?: number;
    steps?: number;
    seeds?: ReadonlyMap<string, number>;
  } = {},
): Map<string, number> {
  const adjacency = adjacencyOf(model);
  const nodes = [...adjacency.keys()];
  if (nodes.length === 0) return new Map();

  const raw = new Map(
    nodes.map((node) => [node, Math.max(1e-12, seeds.get(node) ?? 1)]),
  );
  const total = [...raw.values()].reduce((sum, value) => sum + value, 0);
  const teleport = new Map(
    nodes.map((node) => [node, raw.get(node)! / total]),
  );
  let rank = new Map(teleport);
  const d = Math.max(0, Math.min(0.999999, damping));

  for (let iteration = 0; iteration < Math.max(1, steps); iteration++) {
    const next = new Map(
      nodes.map((node) => [node, (1 - d) * teleport.get(node)!]),
    );
    let dangling = 0;

    for (const source of nodes) {
      const targets = adjacency.get(source) ?? [];
      const sourceRank = rank.get(source) ?? 0;
      if (targets.length === 0) {
        dangling += sourceRank;
        continue;
      }
      const share = (d * sourceRank) / targets.length;
      for (const target of targets) {
        next.set(target, (next.get(target) ?? 0) + share);
      }
    }

    if (dangling > 0) {
      for (const node of nodes) {
        next.set(
          node,
          (next.get(node) ?? 0) + d * dangling * teleport.get(node)!,
        );
      }
    }
    rank = next;
  }

  const scale = [...rank.values()].reduce((sum, value) => sum + value, 0) || 1;
  return new Map([...rank].map(([node, value]) => [node, value / scale]));
}

export function hits(
  model: GraphModel,
  steps = 32,
): { hubs: Map<string, number>; authorities: Map<string, number> } {
  const adjacency = adjacencyOf(model);
  const incoming = incomingOf(adjacency);
  const nodes = [...adjacency.keys()];
  let hubs = new Map(nodes.map((node) => [node, 1]));
  let authorities = new Map(nodes.map((node) => [node, 1]));

  const normalizeL2 = (values: Map<string, number>): Map<string, number> => {
    const norm =
      Math.sqrt(
        [...values.values()].reduce((sum, value) => sum + value * value, 0),
      ) || 1;
    return new Map([...values].map(([key, value]) => [key, value / norm]));
  };

  for (let iteration = 0; iteration < Math.max(1, steps); iteration++) {
    const nextAuthorities = normalizeL2(
      new Map(
        nodes.map((node) => [
          node,
          (incoming.get(node) ?? []).reduce(
            (sum, source) => sum + (hubs.get(source) ?? 0),
            0,
          ),
        ]),
      ),
    );
    const nextHubs = normalizeL2(
      new Map(
        nodes.map((node) => [
          node,
          (adjacency.get(node) ?? []).reduce(
            (sum, target) => sum + (nextAuthorities.get(target) ?? 0),
            0,
          ),
        ]),
      ),
    );
    hubs = nextHubs;
    authorities = nextAuthorities;
  }

  return { hubs, authorities };
}

export function katz(
  model: GraphModel,
  {
    alpha,
    beta = 1,
    steps = 40,
  }: { alpha?: number; beta?: number; steps?: number } = {},
): Map<string, number> {
  const adjacency = adjacencyOf(model);
  const incoming = incomingOf(adjacency);
  const nodes = [...adjacency.keys()];
  if (nodes.length === 0) return new Map();

  const maximumDegree = Math.max(
    1,
    ...[...adjacency.values()].map((targets) => targets.length),
  );
  const attenuation = alpha ?? 0.85 / maximumDegree;
  let scores = new Map(nodes.map((node) => [node, 1]));

  for (let iteration = 0; iteration < Math.max(1, steps); iteration++) {
    const next = new Map(
      nodes.map((node) => [
        node,
        beta +
          attenuation *
            (incoming.get(node) ?? []).reduce(
              (sum, source) => sum + (scores.get(source) ?? 0),
              0,
            ),
      ]),
    );
    const maximum = Math.max(1e-12, ...next.values());
    scores = new Map(
      [...next].map(([node, value]) => [node, value / maximum]),
    );
  }
  return scores;
}

export function tarjanScc(model: GraphModel): string[][] {
  const adjacency = adjacencyOf(model);
  const nodes = [...adjacency.keys()];
  let index = 0;
  const stack: string[] = [];
  const onStack = new Set<string>();
  const indices = new Map<string, number>();
  const lowlink = new Map<string, number>();
  const components: string[][] = [];

  const visit = (node: string): void => {
    indices.set(node, index);
    lowlink.set(node, index);
    index++;
    stack.push(node);
    onStack.add(node);

    for (const target of adjacency.get(node) ?? []) {
      if (!indices.has(target)) {
        visit(target);
        lowlink.set(
          node,
          Math.min(lowlink.get(node)!, lowlink.get(target)!),
        );
      } else if (onStack.has(target)) {
        lowlink.set(
          node,
          Math.min(lowlink.get(node)!, indices.get(target)!),
        );
      }
    }

    if (lowlink.get(node) === indices.get(node)) {
      const component: string[] = [];
      while (stack.length > 0) {
        const member = stack.pop()!;
        onStack.delete(member);
        component.push(member);
        if (member === node) break;
      }
      component.sort();
      components.push(component);
    }
  };

  for (const node of nodes) if (!indices.has(node)) visit(node);
  return components.sort(
    (a, b) =>
      (a[0] ?? "").localeCompare(b[0] ?? "") || a.length - b.length,
  );
}

export function brandesBetweenness(model: GraphModel): Map<string, number> {
  const adjacency = adjacencyOf(model);
  const nodes = [...adjacency.keys()];
  const score = new Map(nodes.map((node) => [node, 0]));

  for (const source of nodes) {
    const stack: string[] = [];
    const predecessors = new Map(
      nodes.map((node) => [node, [] as string[]]),
    );
    const sigma = new Map(nodes.map((node) => [node, 0]));
    sigma.set(source, 1);
    const distance = new Map(nodes.map((node) => [node, -1]));
    distance.set(source, 0);
    const queue = [source];

    while (queue.length > 0) {
      const vertex = queue.shift()!;
      stack.push(vertex);
      for (const target of adjacency.get(vertex) ?? []) {
        if (distance.get(target)! < 0) {
          queue.push(target);
          distance.set(target, distance.get(vertex)! + 1);
        }
        if (distance.get(target) === distance.get(vertex)! + 1) {
          sigma.set(
            target,
            (sigma.get(target) ?? 0) + (sigma.get(vertex) ?? 0),
          );
          predecessors.get(target)!.push(vertex);
        }
      }
    }

    const dependency = new Map(nodes.map((node) => [node, 0]));
    while (stack.length > 0) {
      const target = stack.pop()!;
      const targetSigma = sigma.get(target) ?? 0;
      if (targetSigma > 0) {
        const coefficient =
          (1 + (dependency.get(target) ?? 0)) / targetSigma;
        for (const predecessor of predecessors.get(target) ?? []) {
          dependency.set(
            predecessor,
            (dependency.get(predecessor) ?? 0) +
              (sigma.get(predecessor) ?? 0) * coefficient,
          );
        }
      }
      if (target !== source) {
        score.set(
          target,
          (score.get(target) ?? 0) + (dependency.get(target) ?? 0),
        );
      }
    }
  }

  const maximum = Math.max(1e-12, ...score.values());
  return new Map([...score].map(([node, value]) => [node, value / maximum]));
}

export function kCore(model: GraphModel): Map<string, number> {
  const adjacency = adjacencyOf(model);
  const undirected = new Map<string, Set<string>>(
    [...adjacency.keys()].map((node) => [node, new Set()]),
  );
  for (const [source, targets] of adjacency) {
    for (const target of targets) {
      undirected.get(source)!.add(target);
      undirected.get(target)!.add(source);
    }
  }

  const degree = new Map(
    [...undirected].map(([node, neighbors]) => [node, neighbors.size]),
  );
  const removed = new Set<string>();
  const core = new Map<string, number>();
  let degeneracy = 0;

  while (removed.size < undirected.size) {
    const candidates = [...degree]
      .filter(([node]) => !removed.has(node))
      .sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]));
    const [node, currentDegree] = candidates[0]!;
    removed.add(node);
    degeneracy = Math.max(degeneracy, currentDegree);
    core.set(node, degeneracy);
    for (const neighbor of undirected.get(node) ?? []) {
      if (!removed.has(neighbor)) {
        degree.set(neighbor, Math.max(0, (degree.get(neighbor) ?? 0) - 1));
      }
    }
  }

  const maximum = Math.max(1, ...core.values());
  return new Map(
    [...undirected.keys()].map((node) => [
      node,
      (core.get(node) ?? 0) / maximum,
    ]),
  );
}

export function centralities(
  model: GraphModel,
  seeds = new Map<string, number>(),
): CentralityBundle {
  const pageRankValues = pageRank(model, { seeds });
  const { hubs, authorities } = hits(model);
  return {
    pageRank: pageRankValues,
    hubs,
    authorities,
    katz: katz(model),
    betweenness: brandesBetweenness(model),
    core: kCore(model),
    components: tarjanScc(model),
  };
}

const normalizedAt = (
  values: ReadonlyMap<string, number>,
  node: string,
): number => {
  const maximum = Math.max(1e-12, ...values.values());
  return (values.get(node) ?? 0) / maximum;
};

export function graphConsensus(
  model: GraphModel,
  seeds = new Map<string, number>(),
): Map<string, { consensus: number; disagreement: number; votes: number[] }> {
  const bundle = centralities(model, seeds);
  const cyclic = new Set(
    bundle.components
      .filter((component) => component.length > 1)
      .flat(),
  );
  const result = new Map<
    string,
    { consensus: number; disagreement: number; votes: number[] }
  >();

  for (const node of nodesOf(model)) {
    const votes = [
      normalizedAt(bundle.pageRank, node),
      normalizedAt(bundle.hubs, node),
      normalizedAt(bundle.authorities, node),
      bundle.katz.get(node) ?? 0,
      bundle.betweenness.get(node) ?? 0,
      bundle.core.get(node) ?? 0,
      cyclic.has(node) ? 1 : 0,
    ];
    const mean = votes.reduce((sum, value) => sum + value, 0) / votes.length;
    const variance =
      votes.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
      votes.length;
    const disagreement = clamp01(Math.sqrt(variance) * 2);
    result.set(node, {
      consensus: clamp01(mean * (1 - 0.16 * disagreement)),
      disagreement,
      votes,
    });
  }
  return result;
}

export function graphFromDependencies(
  repositories: readonly {
    name: string;
    ecosystem?: string;
    dependencies?: readonly string[];
  }[],
): GraphModel {
  const nodes = repositories.map((repository) => ({
    id: repository.name,
    label: repository.name,
    ecosystem: repository.ecosystem,
  }));
  const known = new Set(nodes.map((node) => node.id));
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();

  for (const repository of repositories) {
    for (const dependency of repository.dependencies ?? []) {
      if (!known.has(dependency) || dependency === repository.name) continue;
      const key = `${repository.name}\u0000${dependency}`;
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push({ source: repository.name, target: dependency });
    }
  }
  return { nodes, edges };
}
