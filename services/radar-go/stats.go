package radar

import (
	"math"
	"sort"
)

func Clamp01(value float64) float64 {
	if value < 0 {
		return 0
	}
	if value > 1 {
		return 1
	}
	return value
}

func StableSigmoid(value float64) float64 {
	if value >= 0 {
		z := math.Exp(-value)
		return 1 / (1 + z)
	}
	z := math.Exp(value)
	return z / (1 + z)
}

func finite(values []float64) []float64 {
	out := make([]float64, 0, len(values))
	for _, value := range values {
		if !math.IsNaN(value) && !math.IsInf(value, 0) {
			out = append(out, value)
		}
	}
	return out
}

func Median(values []float64) float64 {
	xs := finite(values)
	if len(xs) == 0 {
		return 0
	}
	sort.Float64s(xs)
	middle := len(xs) / 2
	if len(xs)%2 == 0 {
		return (xs[middle-1] + xs[middle]) / 2
	}
	return xs[middle]
}

func MAD(values []float64, center *float64) float64 {
	xs := finite(values)
	if len(xs) == 0 {
		return 1
	}
	c := Median(xs)
	if center != nil {
		c = *center
	}
	deviations := make([]float64, len(xs))
	for i, value := range xs {
		deviations[i] = math.Abs(value - c)
	}
	scale := 1.4826 * Median(deviations)
	if scale < 1e-9 {
		return 1e-9
	}
	return scale
}

func HuberLocation(values []float64, delta float64, iterations int) float64 {
	xs := finite(values)
	if len(xs) == 0 {
		return 0
	}
	location := Median(xs)
	scale := MAD(xs, &location)
	if scale <= 1e-12 {
		return location
	}
	if iterations < 1 {
		iterations = 1
	}

	for iteration := 0; iteration < iterations; iteration++ {
		threshold := math.Max(delta, 1e-6) * scale
		numerator := 0.0
		denominator := 0.0
		for _, value := range xs {
			residual := value - location
			absolute := math.Abs(residual)
			weight := 1.0
			if absolute > threshold {
				weight = threshold / math.Max(absolute, 1e-12)
			}
			numerator += weight * value
			denominator += weight
		}
		updated := numerator / math.Max(denominator, 1e-12)
		if math.Abs(updated-location) <= 1e-9*math.Max(1, math.Abs(location)) {
			return updated
		}
		location = updated
	}
	return location
}

func HampelOutlierFraction(values []float64, threshold float64) float64 {
	xs := finite(values)
	if len(xs) == 0 {
		return 0
	}
	center := Median(xs)
	scale := MAD(xs, &center)
	if scale <= 1e-12 {
		return 0
	}
	outliers := 0
	for _, value := range xs {
		if math.Abs(value-center) > threshold*scale {
			outliers++
		}
	}
	return float64(outliers) / float64(len(xs))
}

func TheilSenSlope(values []float64) float64 {
	xs := finite(values)
	if len(xs) < 2 {
		return 0
	}
	slopes := make([]float64, 0, len(xs)*(len(xs)-1)/2)
	for left := 0; left < len(xs)-1; left++ {
		for right := left + 1; right < len(xs); right++ {
			slopes = append(slopes, (xs[right]-xs[left])/float64(right-left))
		}
	}
	return Median(slopes)
}

func WinsorizedVariance(values []float64, clipZ float64) float64 {
	xs := finite(values)
	if len(xs) < 2 {
		return 0
	}
	center := HuberLocation(xs, 1.345, 16)
	scale := MAD(xs, &center)
	low := center - math.Max(clipZ, 0)*scale
	high := center + math.Max(clipZ, 0)*scale
	clipped := make([]float64, len(xs))
	mean := 0.0
	for i, value := range xs {
		clipped[i] = math.Max(low, math.Min(high, value))
		mean += clipped[i]
	}
	mean /= float64(len(clipped))
	variance := 0.0
	for _, value := range clipped {
		delta := value - mean
		variance += delta * delta
	}
	return variance / float64(len(clipped)-1)
}

func TrimmedMean(values []float64, fraction float64) float64 {
	xs := finite(values)
	if len(xs) == 0 {
		return 0
	}
	sort.Float64s(xs)
	fraction = math.Max(0, math.Min(0.49, fraction))
	trim := int(math.Floor(float64(len(xs)) * fraction))
	if trim > len(xs)/2 {
		trim = len(xs) / 2
	}
	xs = xs[trim : len(xs)-trim]
	total := 0.0
	for _, value := range xs {
		total += value
	}
	return total / float64(len(xs))
}

func CVaR(values []float64, quantile float64) float64 {
	if len(values) == 0 {
		return 0
	}
	xs := make([]float64, len(values))
	for i, value := range values {
		xs[i] = Clamp01(value)
	}
	sort.Float64s(xs)
	quantile = math.Max(0.5, math.Min(0.999999, quantile))
	start := int(math.Floor(float64(len(xs)) * quantile))
	if start >= len(xs) {
		start = len(xs) - 1
	}
	total := 0.0
	for _, value := range xs[start:] {
		total += value
	}
	return total / float64(len(xs)-start)
}

type OnlineMoments struct {
	N    uint64
	Mean float64
	M2   float64
}

func (m *OnlineMoments) Push(value float64) {
	m.N++
	delta := value - m.Mean
	m.Mean += delta / float64(m.N)
	m.M2 += delta * (value - m.Mean)
}

func (m OnlineMoments) Variance() float64 {
	if m.N < 2 {
		return 0
	}
	return m.M2 / float64(m.N-1)
}

func (m OnlineMoments) StandardDeviation() float64 {
	return math.Sqrt(math.Max(0, m.Variance()))
}

func (m OnlineMoments) StandardError() float64 {
	if m.N == 0 {
		return 0
	}
	return m.StandardDeviation() / math.Sqrt(float64(m.N))
}
