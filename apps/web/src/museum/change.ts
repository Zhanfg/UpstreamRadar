import type { Vote } from "./types.js";
import {
  clamp01,
  mad,
  median,
  theilSenSlope,
} from "./statistics.js";

export interface BOCPDResult {
  resetProbability: number;
  expectedRunLength: number;
  posterior: number[];
}

export function cusumScore(
  values: readonly number[],
  drift = 0.02,
): number {
  if (values.length < 2) return 0;
  const xs = values.map(clamp01);
  const mean = xs.reduce((sum, value) => sum + value, 0) / xs.length;
  let positive = 0;
  let negative = 0;
  let maximum = 0;
  for (const value of xs) {
    const residual = value - mean;
    positive = Math.max(0, positive + residual - drift);
    negative = Math.min(0, negative + residual + drift);
    maximum = Math.max(maximum, positive, -negative);
  }
  return clamp01(1 - Math.exp(-2.4 * maximum));
}

export function pageHinkleyScore(
  values: readonly number[],
  delta = 0.04,
  scale = 1.25,
): number {
  if (values.length < 2) return 0;
  const xs = values.map(clamp01);
  let runningMean = 0;
  let cumulative = 0;
  let minimum = 0;
  let peak = 0;

  xs.forEach((value, index) => {
    const count = index + 1;
    runningMean += (value - runningMean) / count;
    cumulative += value - runningMean - delta;
    minimum = Math.min(minimum, cumulative);
    peak = Math.max(peak, cumulative - minimum);
  });
  return clamp01(1 - Math.exp(-peak / Math.max(scale, 1e-9)));
}

export function adwinScore(
  values: readonly number[],
  {
    delta = 0.01,
    minWindow = 3,
  }: { delta?: number; minWindow?: number } = {},
): number {
  const xs = values.map(clamp01);
  const width = Math.max(1, Math.floor(minWindow));
  if (xs.length < 2 * width) return 0;

  const prefix = [0];
  for (const value of xs) {
    prefix.push(prefix[prefix.length - 1]! + value);
  }
  const confidence = Math.max(1e-12, Math.min(0.5, delta));
  const logTerm = Math.log(4 / confidence);
  let strongest = 0;

  for (let cut = width; cut <= xs.length - width; cut++) {
    const n0 = cut;
    const n1 = xs.length - cut;
    const mean0 = prefix[cut]! / n0;
    const mean1 = (prefix[xs.length]! - prefix[cut]!) / n1;
    const epsilon = Math.sqrt(0.5 * logTerm * (1 / n0 + 1 / n1));
    const excess = Math.abs(mean1 - mean0) - epsilon;
    if (excess > 0) {
      strongest = Math.max(strongest, excess / (1 + epsilon));
    }
  }
  return clamp01(strongest * 2.5);
}

export function bernoulliBOCPD(
  observations: readonly number[],
  {
    hazard = 0.08,
    priorAlpha = 1,
    priorBeta = 1,
    maxRunLength = 64,
  }: {
    hazard?: number;
    priorAlpha?: number;
    priorBeta?: number;
    maxRunLength?: number;
  } = {},
): BOCPDResult {
  if (observations.length === 0) {
    return { resetProbability: 0, expectedRunLength: 0, posterior: [1] };
  }
  const h = Math.max(1e-6, Math.min(0.95, hazard));
  const a0 = Math.max(1e-9, priorAlpha);
  const b0 = Math.max(1e-9, priorBeta);

  let probabilities = [1];
  let alphas = [a0];
  let betas = [b0];

  for (const raw of observations) {
    const observation = raw === 0 ? 0 : 1;
    const length = Math.min(probabilities.length, maxRunLength + 1);
    const nextSize = Math.min(length + 1, maxRunLength + 1);
    const nextProbability = Array(nextSize).fill(0) as number[];
    const nextAlpha = Array(nextSize).fill(a0) as number[];
    const nextBeta = Array(nextSize).fill(b0) as number[];

    const priorPredictive =
      observation === 1 ? a0 / (a0 + b0) : b0 / (a0 + b0);
    const previousMass = probabilities
      .slice(0, length)
      .reduce((sum, value) => sum + value, 0);
    nextProbability[0] = h * priorPredictive * previousMass;
    nextAlpha[0] = a0 + observation;
    nextBeta[0] = b0 + (1 - observation);

    for (let runLength = 0; runLength < length; runLength++) {
      const target = runLength + 1;
      if (target >= nextSize) continue;
      const alpha = alphas[runLength]!;
      const beta = betas[runLength]!;
      const predictive =
        observation === 1
          ? alpha / (alpha + beta)
          : beta / (alpha + beta);
      nextProbability[target] =
        probabilities[runLength]! * predictive * (1 - h);
      nextAlpha[target] = alpha + observation;
      nextBeta[target] = beta + (1 - observation);
    }

    const total = nextProbability.reduce((sum, value) => sum + value, 0);
    probabilities =
      total <= 1e-15
        ? [1, ...Array(nextSize - 1).fill(0)]
        : nextProbability.map((value) => value / total);
    alphas = nextAlpha;
    betas = nextBeta;
  }

  return {
    resetProbability: clamp01(probabilities[0] ?? 0),
    expectedRunLength: probabilities.reduce(
      (sum, probability, index) => sum + index * probability,
      0,
    ),
    posterior: probabilities,
  };
}

export function changeVotes(
  impactHistory: readonly number[],
  changeHistory: readonly number[],
): Vote[] {
  const normalized =
    impactHistory.length > 0
      ? impactHistory.map((value) => clamp01(value / 10))
      : changeHistory.map((value) => (value === 0 ? 0 : 1));

  const bocpd =
    changeHistory.length > 0
      ? bernoulliBOCPD(changeHistory).resetProbability
      : 0;

  let jump = 0;
  if (normalized.length >= 2) {
    const prior = normalized.slice(0, -1);
    const center = median(prior);
    const scale = mad(prior, center);
    jump = clamp01(
      Math.abs(normalized[normalized.length - 1]! - center) /
        (1.35 * Math.max(scale, 1e-9)),
    );
  }

  return [
    { exhibit: "cusum", score: cusumScore(normalized) },
    { exhibit: "page-hinkley", score: pageHinkleyScore(normalized) },
    { exhibit: "adwin", score: adwinScore(normalized) },
    { exhibit: "bocpd-beta", score: bocpd },
    { exhibit: "robust-jump", score: jump },
    {
      exhibit: "theil-sen",
      score: clamp01(Math.abs(theilSenSlope(normalized)) * 4),
    },
  ];
}

export function changeConsensus(
  impactHistory: readonly number[],
  changeHistory: readonly number[],
): { consensus: number; disagreement: number; votes: Vote[] } {
  const votes = changeVotes(impactHistory, changeHistory);
  const mean = votes.reduce((sum, vote) => sum + vote.score, 0) / votes.length;
  const variance =
    votes.reduce((sum, vote) => sum + (vote.score - mean) ** 2, 0) /
    votes.length;
  const disagreement = clamp01(Math.sqrt(variance) * 2);
  return {
    consensus: clamp01(mean * (1 - 0.22 * disagreement)),
    disagreement,
    votes,
  };
}
