import type { DistributionShift, Vote } from "./types.js";

const EPS = 1e-12;
export const clamp01 = (value: number): number =>
  Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));

const finite = (values: readonly number[]): number[] =>
  values.filter(Number.isFinite).map(Number);

export function median(values: readonly number[]): number {
  const xs = finite(values).sort((a, b) => a - b);
  if (xs.length === 0) return 0;
  const middle = Math.floor(xs.length / 2);
  return xs.length % 2 === 0
    ? (xs[middle - 1]! + xs[middle]!) / 2
    : xs[middle]!;
}

export function mad(
  values: readonly number[],
  center = median(values),
): number {
  const deviations = finite(values).map((value) => Math.abs(value - center));
  if (deviations.length === 0) return 1;
  return Math.max(1e-9, 1.4826 * median(deviations));
}

export function huberLocation(
  values: readonly number[],
  delta = 1.345,
  iterations = 16,
): number {
  const xs = finite(values);
  if (xs.length === 0) return 0;
  let location = median(xs);
  const scale = mad(xs, location);
  if (scale <= EPS) return location;

  for (let iteration = 0; iteration < Math.max(1, iterations); iteration++) {
    const threshold = Math.max(delta, 1e-6) * scale;
    let numerator = 0;
    let denominator = 0;
    for (const value of xs) {
      const residual = value - location;
      const absolute = Math.abs(residual);
      const weight =
        absolute <= threshold ? 1 : threshold / Math.max(absolute, EPS);
      numerator += weight * value;
      denominator += weight;
    }
    const updated = numerator / Math.max(denominator, EPS);
    if (
      Math.abs(updated - location) <=
      1e-9 * Math.max(1, Math.abs(location))
    ) {
      return updated;
    }
    location = updated;
  }
  return location;
}

export function hampelOutlierFraction(
  values: readonly number[],
  threshold = 3,
): number {
  const xs = finite(values);
  if (xs.length === 0) return 0;
  const center = median(xs);
  const scale = mad(xs, center);
  if (scale <= EPS) return 0;
  return (
    xs.filter((value) => Math.abs(value - center) > threshold * scale).length /
    xs.length
  );
}

export function theilSenSlope(values: readonly number[]): number {
  const xs = finite(values);
  if (xs.length < 2) return 0;
  const slopes: number[] = [];
  for (let left = 0; left < xs.length - 1; left++) {
    for (let right = left + 1; right < xs.length; right++) {
      slopes.push((xs[right]! - xs[left]!) / (right - left));
    }
  }
  return median(slopes);
}

export function winsorizedVariance(
  values: readonly number[],
  clipZ = 3.5,
): number {
  const xs = finite(values);
  if (xs.length < 2) return 0;
  const center = huberLocation(xs);
  const scale = mad(xs, center);
  const low = center - Math.max(0, clipZ) * scale;
  const high = center + Math.max(0, clipZ) * scale;
  const clipped = xs.map((value) => Math.max(low, Math.min(high, value)));
  const mean = clipped.reduce((sum, value) => sum + value, 0) / clipped.length;
  return (
    clipped.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
    (clipped.length - 1)
  );
}

const normalizeDistribution = (values: readonly number[]): number[] => {
  if (values.length === 0) return [];
  const positive = values.map((value) => Math.max(0, value));
  const total = positive.reduce((sum, value) => sum + value, 0);
  if (total <= EPS) return positive.map(() => 1 / positive.length);
  return positive.map((value) => value / total);
};

export function entropy(values: readonly number[]): number {
  return normalizeDistribution(values).reduce(
    (sum, probability) =>
      probability > EPS
        ? sum - probability * Math.log2(probability)
        : sum,
    0,
  );
}

const kl = (left: readonly number[], right: readonly number[]): number =>
  left.reduce((sum, probability, index) => {
    const q = right[index] ?? 0;
    return probability > EPS && q > EPS
      ? sum + probability * Math.log2(probability / q)
      : sum;
  }, 0);

export function jensenShannon(
  left: readonly number[],
  right: readonly number[],
): number {
  const size = Math.max(left.length, right.length);
  if (size === 0) return 0;
  const l = normalizeDistribution([
    ...left,
    ...Array(size - left.length).fill(0),
  ]);
  const r = normalizeDistribution([
    ...right,
    ...Array(size - right.length).fill(0),
  ]);
  const midpoint = l.map((value, index) => (value + (r[index] ?? 0)) / 2);
  return clamp01(0.5 * kl(l, midpoint) + 0.5 * kl(r, midpoint));
}

const quantile = (sorted: readonly number[], q: number): number => {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0]!;
  const position = clamp01(q) * (sorted.length - 1);
  const lower = Math.floor(position);
  const upper = Math.min(sorted.length - 1, lower + 1);
  const fraction = position - lower;
  return (
    sorted[lower]! * (1 - fraction) + sorted[upper]! * fraction
  );
};

export function wasserstein1D(
  left: readonly number[],
  right: readonly number[],
): number {
  if (left.length === 0 && right.length === 0) return 0;
  if (left.length === 0 || right.length === 0) return 1;
  const a = left.map(clamp01).sort((x, y) => x - y);
  const b = right.map(clamp01).sort((x, y) => x - y);
  const samples = Math.max(2, a.length, b.length);
  let total = 0;
  for (let index = 0; index < samples; index++) {
    const q = index / (samples - 1);
    total += Math.abs(quantile(a, q) - quantile(b, q));
  }
  return clamp01(total / samples);
}

export function maximumMeanDiscrepancy(
  left: readonly number[],
  right: readonly number[],
  explicitBandwidth?: number,
): number {
  if (left.length === 0 && right.length === 0) return 0;
  if (left.length === 0 || right.length === 0) return 1;
  const a = left.map(clamp01);
  const b = right.map(clamp01);
  let bandwidth = explicitBandwidth ?? 0;

  if (!(bandwidth > 0)) {
    const combined = [...a, ...b];
    const distances: number[] = [];
    for (let i = 0; i < combined.length - 1; i++) {
      for (let j = i + 1; j < combined.length; j++) {
        const distance = Math.abs(combined[i]! - combined[j]!);
        if (distance > EPS) distances.push(distance);
      }
    }
    bandwidth = distances.length > 0 ? median(distances) : 0.1;
  }
  bandwidth = Math.max(1e-6, bandwidth);

  const kernel = (x: number, y: number): number => {
    const distance = x - y;
    return Math.exp(-(distance * distance) / (2 * bandwidth * bandwidth));
  };
  const averageKernel = (
    xs: readonly number[],
    ys: readonly number[],
  ): number =>
    xs.reduce(
      (outer, x) =>
        outer + ys.reduce((inner, y) => inner + kernel(x, y), 0),
      0,
    ) /
    (xs.length * ys.length);

  const mmd2 =
    averageKernel(a, a) + averageKernel(b, b) - 2 * averageKernel(a, b);
  return clamp01(Math.sqrt(Math.max(0, mmd2) / 2));
}

const histogram = (
  values: readonly number[],
  bins = 4,
): number[] => {
  const out = Array(Math.max(1, bins)).fill(0) as number[];
  for (const value of values) {
    const index = Math.min(
      out.length - 1,
      Math.floor(clamp01(value) * out.length),
    );
    out[index] = (out[index] ?? 0) + 1;
  }
  return out;
};

export function distributionShift(
  values: readonly number[],
): DistributionShift {
  const xs = values.map(clamp01);
  if (xs.length < 4) {
    return {
      jsd: 0,
      wasserstein: 0,
      mmd: 0,
      consensus: 0,
      disagreement: 0,
    };
  }
  const split = Math.min(xs.length - 1, Math.max(2, Math.floor(xs.length / 2)));
  const older = xs.slice(0, split);
  const recent = xs.slice(split);

  const jsd = jensenShannon(histogram(older), histogram(recent));
  const wasserstein = wasserstein1D(older, recent);
  const mmd = maximumMeanDiscrepancy(older, recent);
  const maximum = Math.max(jsd, wasserstein, mmd);
  const minimum = Math.min(jsd, wasserstein, mmd);
  const disagreement = maximum - minimum;
  const consensus = clamp01(
    (0.42 * jsd + 0.30 * wasserstein + 0.28 * mmd) *
      (1 - 0.12 * disagreement),
  );
  return { jsd, wasserstein, mmd, consensus, disagreement };
}

export function cvar(
  values: readonly number[],
  quantileLevel = 0.75,
): number {
  if (values.length === 0) return 0;
  const xs = values.map(clamp01).sort((a, b) => a - b);
  const q = Math.max(0.5, Math.min(0.999999, quantileLevel));
  const start = Math.min(
    xs.length - 1,
    Math.floor(xs.length * q),
  );
  return (
    xs.slice(start).reduce((sum, value) => sum + value, 0) /
    (xs.length - start)
  );
}

export function galleryConsensus(votes: readonly Vote[]): {
  consensus: number;
  disagreement: number;
} {
  if (votes.length === 0) return { consensus: 0, disagreement: 0 };
  const mean = votes.reduce((sum, vote) => sum + vote.score, 0) / votes.length;
  const variance =
    votes.reduce((sum, vote) => sum + (vote.score - mean) ** 2, 0) /
    votes.length;
  const disagreement = clamp01(Math.sqrt(variance) * 2);
  return {
    consensus: clamp01(mean * (1 - 0.22 * disagreement)),
    disagreement,
  };
}
