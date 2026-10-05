import type { ParetoPoint, PortfolioAudit } from "./types.js";

export interface OptimizationItem extends ParetoPoint {
  cost: number;
  tags: readonly string[];
}

export function exactKnapsack(
  items: readonly OptimizationItem[],
  budget: number,
): string[] {
  const capacity = Math.max(0, Math.floor(budget));
  type State = { utility: number; names: string[] };
  const dp: State[] = Array.from({ length: capacity + 1 }, () => ({
    utility: 0,
    names: [],
  }));

  for (const item of items) {
    const cost = Math.max(1, Math.floor(item.cost));
    if (cost > capacity) continue;
    for (let current = capacity; current >= cost; current--) {
      const previous = dp[current - cost]!;
      const names = [...previous.names, item.name].sort();
      const candidate = previous.utility + item.utility;
      const existing = dp[current]!;
      if (
        candidate > existing.utility + 1e-12 ||
        (Math.abs(candidate - existing.utility) <= 1e-12 &&
          names.join("\u0000") < existing.names.join("\u0000"))
      ) {
        dp[current] = { utility: candidate, names };
      }
    }
  }

  return dp
    .reduce((best, state) => {
      if (state.utility > best.utility + 1e-12) return state;
      if (
        Math.abs(state.utility - best.utility) <= 1e-12 &&
        state.names.join("\u0000") < best.names.join("\u0000")
      ) {
        return state;
      }
      return best;
    }, { utility: 0, names: [] } as State)
    .names;
}

export function epsilonPareto(
  points: readonly ParetoPoint[],
  epsilon = 1e-6,
): ParetoPoint[] {
  const e = Math.max(0, epsilon);
  const dominates = (left: ParetoPoint, right: ParetoPoint): boolean => {
    const weak =
      left.utility + e >= right.utility &&
      left.novelty + e >= right.novelty &&
      left.risk <= right.risk + e;
    const strict =
      left.utility > right.utility + e ||
      left.novelty > right.novelty + e ||
      left.risk + e < right.risk;
    return weak && strict;
  };

  return points.filter(
    (candidate, index) =>
      !points.some(
        (other, otherIndex) =>
          otherIndex !== index && dominates(other, candidate),
      ),
  );
}

const coveredTags = (
  selected: ReadonlySet<string>,
  byName: ReadonlyMap<string, OptimizationItem>,
): Set<string> => {
  const covered = new Set<string>();
  for (const name of selected) {
    for (const tag of byName.get(name)?.tags ?? []) covered.add(tag);
  }
  return covered;
};

export function celfSelect(
  items: readonly OptimizationItem[],
  budget: number,
): string[] {
  const byName = new Map(items.map((item) => [item.name, item]));
  const selected = new Set<string>();
  const cache = new Map<string, { gain: number; stamp: number }>();
  let spent = 0;

  const marginal = (item: OptimizationItem): number => {
    const covered = coveredTags(selected, byName);
    const unique = new Set(item.tags);
    const newTags = [...unique].filter((tag) => !covered.has(tag)).length;
    return (
      newTags +
      0.5 * item.utility +
      0.25 * item.novelty -
      0.15 * item.risk
    );
  };

  for (const item of items) {
    cache.set(item.name, { gain: marginal(item), stamp: 0 });
  }

  while (cache.size > 0) {
    let best: string | undefined;
    let bestRatio = Number.NEGATIVE_INFINITY;
    let bestGain = Number.NEGATIVE_INFINITY;
    for (const [name, entry] of cache) {
      const item = byName.get(name)!;
      const ratio = entry.gain / Math.max(1, item.cost);
      if (
        ratio > bestRatio ||
        (ratio === bestRatio &&
          (entry.gain > bestGain ||
            (entry.gain === bestGain && (best === undefined || name < best))))
      ) {
        best = name;
        bestRatio = ratio;
        bestGain = entry.gain;
      }
    }
    if (best === undefined) break;

    const entry = cache.get(best)!;
    if (entry.stamp !== selected.size) {
      cache.set(best, {
        gain: marginal(byName.get(best)!),
        stamp: selected.size,
      });
      continue;
    }
    cache.delete(best);

    const item = byName.get(best)!;
    if (spent + item.cost > budget) continue;
    if (entry.gain <= 0) break;
    selected.add(best);
    spent += item.cost;
  }

  return [...selected].sort();
}

export function portfolioUtility(
  selected: readonly string[],
  items: readonly OptimizationItem[],
  coverageBonus = 0.08,
  redundancyPenalty = 0.10,
): number {
  const byName = new Map(items.map((item) => [item.name, item]));
  const counts = new Map<string, number>();
  let total = 0;

  for (const name of selected) {
    const item = byName.get(name);
    if (!item) continue;
    total += item.utility;
    for (const tag of new Set(item.tags)) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }

  const duplicates = [...counts.values()].reduce(
    (sum, count) => sum + Math.max(0, count - 1),
    0,
  );
  return (
    total +
    coverageBonus * counts.size -
    redundancyPenalty * duplicates
  );
}

export function auditPortfolio(
  items: readonly OptimizationItem[],
  budget: number,
  production: readonly string[],
): PortfolioAudit {
  const exact = exactKnapsack(items, budget);
  const celf = celfSelect(items, budget);
  const pareto = epsilonPareto(items).map((item) => item.name).sort();
  const byName = new Map(items.map((item) => [item.name, item]));
  const sumUtility = (names: readonly string[]): number =>
    names.reduce((sum, name) => sum + (byName.get(name)?.utility ?? 0), 0);
  const productionUtility = sumUtility(production);
  const exactUtility = sumUtility(exact);

  return {
    production: [...production].sort(),
    exactKnapsack: exact,
    celf,
    pareto,
    utilityRatio:
      exactUtility > 0 ? Math.min(1, productionUtility / exactUtility) : 1,
  };
}
