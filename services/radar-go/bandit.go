package radar

import "math"

const banditEpsilon = 1e-12

func BernoulliKL(p0, q0 float64) float64 {
	p := math.Max(banditEpsilon, math.Min(1-banditEpsilon, p0))
	q := math.Max(banditEpsilon, math.Min(1-banditEpsilon, q0))
	return p*math.Log(p/q) + (1-p)*math.Log((1-p)/(1-q))
}

func UCBV(mean, variance float64, pulls, totalPulls int) float64 {
	if pulls <= 0 {
		return 1
	}
	logTerm := math.Log(float64(maxInt(totalPulls, 2)))
	bonus := math.Sqrt(2*math.Max(variance, 0)*logTerm/float64(pulls)) +
		3*logTerm/float64(pulls)
	return Clamp01(mean + bonus)
}

func KLUCB(mean float64, pulls, totalPulls int, precision float64) float64 {
	mean = Clamp01(mean)
	if pulls <= 0 {
		return 1
	}
	total := float64(maxInt(totalPulls, 2))
	budget := (math.Log(total) + 3*math.Log(math.Max(math.Log(total), 1))) / float64(pulls)
	low, high := mean, 1-banditEpsilon
	for high-low > math.Max(precision, 1e-12) {
		middle := (low + high) / 2
		if BernoulliKL(mean, middle) <= budget {
			low = middle
		} else {
			high = middle
		}
	}
	return Clamp01(low)
}

func betaContinuedFraction(a, b, x float64) float64 {
	const (
		maxIterations = 200
		epsilon       = 3e-14
		fpmin         = 1e-300
	)
	qab := a + b
	qap := a + 1
	qam := a - 1
	c := 1.0
	d := 1 - qab*x/qap
	if math.Abs(d) < fpmin {
		d = fpmin
	}
	d = 1 / d
	h := d

	for m := 1; m <= maxIterations; m++ {
		m2 := 2 * m
		aa := float64(m) * (b-float64(m)) * x /
			((qam+float64(m2))*(a+float64(m2)))
		d = 1 + aa*d
		if math.Abs(d) < fpmin {
			d = fpmin
		}
		c = 1 + aa/c
		if math.Abs(c) < fpmin {
			c = fpmin
		}
		d = 1 / d
		h *= d * c

		aa = -(a+float64(m))*(qab+float64(m))*x /
			((a+float64(m2))*(qap+float64(m2)))
		d = 1 + aa*d
		if math.Abs(d) < fpmin {
			d = fpmin
		}
		c = 1 + aa/c
		if math.Abs(c) < fpmin {
			c = fpmin
		}
		d = 1 / d
		delta := d * c
		h *= delta
		if math.Abs(delta-1) <= epsilon {
			break
		}
	}
	return h
}

func RegularizedBeta(x, a, b float64) float64 {
	x = Clamp01(x)
	if a <= 0 || b <= 0 {
		panic("beta parameters must be positive")
	}
	if x <= 0 {
		return 0
	}
	if x >= 1 {
		return 1
	}
	lgammaAB, _ := math.Lgamma(a + b)
	lgammaA, _ := math.Lgamma(a)
	lgammaB, _ := math.Lgamma(b)
	logBT := lgammaAB - lgammaA - lgammaB +
		a*math.Log(x) + b*math.Log(1-x)
	bt := math.Exp(logBT)
	if x < (a+1)/(a+b+2) {
		return Clamp01(bt * betaContinuedFraction(a, b, x) / a)
	}
	return Clamp01(1 - bt*betaContinuedFraction(b, a, 1-x)/b)
}

func BetaQuantile(probability, alpha, beta, precision float64) float64 {
	probability = Clamp01(probability)
	low, high := 0.0, 1.0
	for high-low > math.Max(precision, 1e-10) {
		middle := (low + high) / 2
		if RegularizedBeta(middle, alpha, beta) < probability {
			low = middle
		} else {
			high = middle
		}
	}
	return Clamp01((low + high) / 2)
}

func BayesUCB(alpha, beta float64, totalPulls int) float64 {
	total := float64(maxInt(totalPulls, 2))
	return BetaQuantile(1-1/total, alpha, beta, 1e-7)
}

func ExplorationVotes(hits, misses, observationCount int, variance float64, totalObservations int) []Vote {
	pulls := maxInt(observationCount, hits+misses)
	mean := (float64(hits) + 0.5) / (float64(hits+misses) + 1)
	deficit := 1 / math.Sqrt(1+float64(pulls))
	return []Vote{
		{Exhibit: "ucb-v", Score: UCBV(mean, variance, pulls, totalObservations)},
		{Exhibit: "kl-ucb", Score: KLUCB(mean, pulls, totalObservations, 1e-7)},
		{Exhibit: "bayes-ucb", Score: BayesUCB(float64(hits)+1, float64(misses)+1, totalObservations)},
		{Exhibit: "information-deficit", Score: Clamp01(deficit)},
	}
}

func maxInt(left, right int) int {
	if left > right {
		return left
	}
	return right
}
