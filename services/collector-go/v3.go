package main

import (
	"math"
	"sort"
)

type OnlineMoments struct {
	N    int
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

func bernoulliKL(q, p float64) float64 {
	const eps = 1e-12
	q = math.Max(eps, math.Min(1-eps, q))
	p = math.Max(eps, math.Min(1-eps, p))
	return q*math.Log(q/p) + (1-q)*math.Log((1-q)/(1-p))
}

func surprise(q, p float64) float64 {
	return math.Max(0, math.Min(1, 1-math.Exp(-3.4*bernoulliKL(q, p))))
}

func cvar(values []float64, quantile float64) float64 {
	if len(values) == 0 {
		return 0
	}
	xs := append([]float64(nil), values...)
	sort.Float64s(xs)
	q := math.Max(0.5, math.Min(0.999999, quantile))
	start := int(math.Floor(float64(len(xs)) * q))
	if start >= len(xs) {
		start = len(xs) - 1
	}
	total := 0.0
	for _, value := range xs[start:] {
		total += math.Max(0, math.Min(1, value))
	}
	return total / float64(len(xs)-start)
}
