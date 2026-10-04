import type { RadarEvent } from "./index.js";

export interface HarmonyV3Projection {
  repository: string;
  impact: number;
  surprise: number;
  tailRisk: number;
  novelty: number;
  utility: number;
}

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

export function bernoulliKL(q: number, p: number): number {
  const eps = 1e-12;
  q = Math.max(eps, Math.min(1 - eps, q));
  p = Math.max(eps, Math.min(1 - eps, p));
  return q * Math.log(q / p) + (1 - q) * Math.log((1 - q) / (1 - p));
}

export function bayesianSurprise(empirical: number, predicted: number): number {
  return clamp01(1 - Math.exp(-3.4 * bernoulliKL(empirical, predicted)));
}

export function paretoFrontier(items: readonly HarmonyV3Projection[]): HarmonyV3Projection[] {
  return items.filter((candidate, index) =>
    !items.some((other, otherIndex) =>
      otherIndex !== index &&
      other.utility >= candidate.utility &&
      other.novelty >= candidate.novelty &&
      other.tailRisk <= candidate.tailRisk &&
      (
        other.utility > candidate.utility ||
        other.novelty > candidate.novelty ||
        other.tailRisk < candidate.tailRisk
      ),
    ),
  );
}

export function eventDiversity(events: readonly RadarEvent[]): number {
  if (events.length < 2) return events.length;
  const repositories = new Set(events.map((event) => event.repository)).size;
  const eventTypes = new Set(events.map((event) => event.event_type)).size;
  return clamp01(
    0.6 * repositories / events.length +
    0.4 * eventTypes / events.length
  );
}
