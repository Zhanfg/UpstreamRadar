package radar

import (
	"math"
	"sort"
)

const informationEpsilon = 1e-12

func normalizeDistribution(values []float64) []float64 {
	if len(values) == 0 {
		return nil
	}
	out := make([]float64, len(values))
	total := 0.0
	for i, value := range values {
		out[i] = math.Max(0, value)
		total += out[i]
	}
	if total <= informationEpsilon {
		for i := range out {
			out[i] = 1 / float64(len(out))
		}
		return out
	}
	for i := range out {
		out[i] /= total
	}
	return out
}

func Entropy(values []float64) float64 {
	total := 0.0
	for _, p := range normalizeDistribution(values) {
		if p > informationEpsilon {
			total -= p * math.Log2(p)
		}
	}
	return total
}

func klDivergence(left, right []float64) float64 {
	total := 0.0
	for i := range left {
		if left[i] > informationEpsilon && right[i] > informationEpsilon {
			total += left[i] * math.Log2(left[i]/right[i])
		}
	}
	return total
}

func JensenShannon(left, right []float64) float64 {
	size := len(left)
	if len(right) > size {
		size = len(right)
	}
	if size == 0 {
		return 0
	}
	l := make([]float64, size)
	r := make([]float64, size)
	copy(l, left)
	copy(r, right)
	l = normalizeDistribution(l)
	r = normalizeDistribution(r)
	midpoint := make([]float64, size)
	for i := range midpoint {
		midpoint[i] = (l[i] + r[i]) / 2
	}
	return Clamp01(0.5*klDivergence(l, midpoint) + 0.5*klDivergence(r, midpoint))
}

func interpolatedQuantile(sorted []float64, q float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	if len(sorted) == 1 {
		return sorted[0]
	}
	position := Clamp01(q) * float64(len(sorted)-1)
	lower := int(math.Floor(position))
	upper := lower + 1
	if upper >= len(sorted) {
		upper = len(sorted) - 1
	}
	fraction := position - float64(lower)
	return sorted[lower]*(1-fraction) + sorted[upper]*fraction
}

func Wasserstein1D(left, right []float64) float64 {
	if len(left) == 0 && len(right) == 0 {
		return 0
	}
	if len(left) == 0 || len(right) == 0 {
		return 1
	}
	a := make([]float64, len(left))
	b := make([]float64, len(right))
	for i, value := range left {
		a[i] = Clamp01(value)
	}
	for i, value := range right {
		b[i] = Clamp01(value)
	}
	sort.Float64s(a)
	sort.Float64s(b)
	samples := len(a)
	if len(b) > samples {
		samples = len(b)
	}
	if samples < 2 {
		samples = 2
	}
	total := 0.0
	for index := 0; index < samples; index++ {
		q := float64(index) / float64(samples-1)
		total += math.Abs(interpolatedQuantile(a, q) - interpolatedQuantile(b, q))
	}
	return Clamp01(total / float64(samples))
}

func MaximumMeanDiscrepancy(left, right []float64, bandwidth float64) float64 {
	if len(left) == 0 && len(right) == 0 {
		return 0
	}
	if len(left) == 0 || len(right) == 0 {
		return 1
	}
	a := make([]float64, len(left))
	b := make([]float64, len(right))
	for i, value := range left {
		a[i] = Clamp01(value)
	}
	for i, value := range right {
		b[i] = Clamp01(value)
	}

	if bandwidth <= 0 {
		combined := append(append([]float64{}, a...), b...)
		distances := make([]float64, 0)
		for i := 0; i < len(combined)-1; i++ {
			for j := i + 1; j < len(combined); j++ {
				distance := math.Abs(combined[i] - combined[j])
				if distance > informationEpsilon {
					distances = append(distances, distance)
				}
			}
		}
		if len(distances) == 0 {
			bandwidth = 0.1
		} else {
			bandwidth = Median(distances)
		}
	}
	bandwidth = math.Max(bandwidth, 1e-6)
	kernel := func(x, y float64) float64 {
		distance := x - y
		return math.Exp(-(distance * distance) / (2 * bandwidth * bandwidth))
	}

	aa := 0.0
	for _, x := range a {
		for _, y := range a {
			aa += kernel(x, y)
		}
	}
	aa /= float64(len(a) * len(a))

	bb := 0.0
	for _, x := range b {
		for _, y := range b {
			bb += kernel(x, y)
		}
	}
	bb /= float64(len(b) * len(b))

	ab := 0.0
	for _, x := range a {
		for _, y := range b {
			ab += kernel(x, y)
		}
	}
	ab /= float64(len(a) * len(b))

	return Clamp01(math.Sqrt(math.Max(0, aa+bb-2*ab) / 2))
}

func histogram(values []float64, bins int) []float64 {
	if bins < 1 {
		bins = 1
	}
	out := make([]float64, bins)
	for _, value := range values {
		index := int(math.Floor(Clamp01(value) * float64(bins)))
		if index >= bins {
			index = bins - 1
		}
		out[index]++
	}
	return out
}

func DistributionShiftVotes(values []float64) []Vote {
	if len(values) < 4 {
		return []Vote{
			{Exhibit: "jsd", Score: 0},
			{Exhibit: "wasserstein-1", Score: 0},
			{Exhibit: "mmd-rbf", Score: 0},
		}
	}
	split := len(values) / 2
	if split < 2 {
		split = 2
	}
	if split >= len(values) {
		split = len(values) - 1
	}
	older := values[:split]
	recent := values[split:]
	return []Vote{
		{Exhibit: "jsd", Score: JensenShannon(histogram(older, 4), histogram(recent, 4))},
		{Exhibit: "wasserstein-1", Score: Wasserstein1D(older, recent)},
		{Exhibit: "mmd-rbf", Score: MaximumMeanDiscrepancy(older, recent, 0)},
	}
}
