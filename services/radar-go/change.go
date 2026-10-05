package radar

import "math"

type BOCPDResult struct {
	ResetProbability  float64   `json:"reset_probability"`
	ExpectedRunLength float64   `json:"expected_run_length"`
	Posterior         []float64 `json:"posterior"`
}

func CUSUMScore(values []float64, drift float64) float64 {
	if len(values) < 2 {
		return 0
	}
	mean := 0.0
	for _, value := range values {
		mean += Clamp01(value)
	}
	mean /= float64(len(values))
	positive, negative, maximum := 0.0, 0.0, 0.0
	for _, raw := range values {
		residual := Clamp01(raw) - mean
		positive = math.Max(0, positive+residual-drift)
		negative = math.Min(0, negative+residual+drift)
		maximum = math.Max(maximum, math.Max(positive, -negative))
	}
	return Clamp01(1 - math.Exp(-2.4*maximum))
}

func PageHinkleyScore(values []float64, delta, scale float64) float64 {
	if len(values) < 2 {
		return 0
	}
	runningMean, cumulative, minimum, peak := 0.0, 0.0, 0.0, 0.0
	for index, raw := range values {
		value := Clamp01(raw)
		count := float64(index + 1)
		runningMean += (value - runningMean) / count
		cumulative += value - runningMean - delta
		minimum = math.Min(minimum, cumulative)
		peak = math.Max(peak, cumulative-minimum)
	}
	return Clamp01(1 - math.Exp(-peak/math.Max(scale, 1e-9)))
}

func ADWINScore(values []float64, delta float64, minWindow int) float64 {
	if minWindow < 1 {
		minWindow = 1
	}
	if len(values) < 2*minWindow {
		return 0
	}
	prefix := make([]float64, len(values)+1)
	for index, raw := range values {
		prefix[index+1] = prefix[index] + Clamp01(raw)
	}
	confidence := math.Max(1e-12, math.Min(0.5, delta))
	logTerm := math.Log(4 / confidence)
	strongest := 0.0

	for cut := minWindow; cut <= len(values)-minWindow; cut++ {
		n0 := float64(cut)
		n1 := float64(len(values) - cut)
		mean0 := prefix[cut] / n0
		mean1 := (prefix[len(values)] - prefix[cut]) / n1
		epsilon := math.Sqrt(0.5 * logTerm * (1/n0 + 1/n1))
		excess := math.Abs(mean1-mean0) - epsilon
		if excess > 0 {
			strongest = math.Max(strongest, excess/(1+epsilon))
		}
	}
	return Clamp01(strongest * 2.5)
}

func BernoulliBOCPD(
	observations []int,
	hazard, priorAlpha, priorBeta float64,
	maxRunLength int,
) BOCPDResult {
	if len(observations) == 0 {
		return BOCPDResult{Posterior: []float64{1}}
	}
	if maxRunLength < 1 {
		maxRunLength = 1
	}
	hazard = math.Max(1e-6, math.Min(0.95, hazard))
	priorAlpha = math.Max(priorAlpha, 1e-9)
	priorBeta = math.Max(priorBeta, 1e-9)

	probabilities := []float64{1}
	alphas := []float64{priorAlpha}
	betas := []float64{priorBeta}

	for _, raw := range observations {
		observation := 0.0
		if raw != 0 {
			observation = 1
		}

		length := len(probabilities)
		if length > maxRunLength+1 {
			length = maxRunLength + 1
		}
		nextSize := length + 1
		if nextSize > maxRunLength+1 {
			nextSize = maxRunLength + 1
		}
		nextProb := make([]float64, nextSize)
		nextAlpha := make([]float64, nextSize)
		nextBeta := make([]float64, nextSize)
		for i := range nextAlpha {
			nextAlpha[i] = priorAlpha
			nextBeta[i] = priorBeta
		}

		priorPredictive := priorBeta / (priorAlpha + priorBeta)
		if observation > 0.5 {
			priorPredictive = priorAlpha / (priorAlpha + priorBeta)
		}
		totalPrevious := 0.0
		for _, value := range probabilities[:length] {
			totalPrevious += value
		}
		nextProb[0] = hazard * priorPredictive * totalPrevious
		nextAlpha[0] = priorAlpha + observation
		nextBeta[0] = priorBeta + (1 - observation)

		for runLength := 0; runLength < length; runLength++ {
			target := runLength + 1
			if target >= nextSize {
				continue
			}
			alpha := alphas[runLength]
			beta := betas[runLength]
			predictive := beta / (alpha + beta)
			if observation > 0.5 {
				predictive = alpha / (alpha + beta)
			}
			nextProb[target] = probabilities[runLength] * predictive * (1 - hazard)
			nextAlpha[target] = alpha + observation
			nextBeta[target] = beta + (1 - observation)
		}

		total := 0.0
		for _, value := range nextProb {
			total += value
		}
		if total <= 1e-15 {
			for i := range nextProb {
				nextProb[i] = 0
			}
			nextProb[0] = 1
		} else {
			for i := range nextProb {
				nextProb[i] /= total
			}
		}
		probabilities, alphas, betas = nextProb, nextAlpha, nextBeta
	}

	expected := 0.0
	for index, probability := range probabilities {
		expected += float64(index) * probability
	}
	return BOCPDResult{
		ResetProbability:  Clamp01(probabilities[0]),
		ExpectedRunLength: expected,
		Posterior:         probabilities,
	}
}

func ChangeVotes(impactHistory []float64, changeHistory []int) []Vote {
	normalized := make([]float64, 0, len(impactHistory))
	for _, value := range impactHistory {
		normalized = append(normalized, Clamp01(value/10))
	}
	if len(normalized) == 0 {
		for _, value := range changeHistory {
			if value == 0 {
				normalized = append(normalized, 0)
			} else {
				normalized = append(normalized, 1)
			}
		}
	}

	bocpd := 0.0
	if len(changeHistory) > 0 {
		bocpd = BernoulliBOCPD(changeHistory, 0.08, 1, 1, 64).ResetProbability
	}
	jump := 0.0
	if len(normalized) >= 2 {
		prior := normalized[:len(normalized)-1]
		center := Median(prior)
		scale := MAD(prior, &center)
		jump = Clamp01(math.Abs(normalized[len(normalized)-1]-center) / (1.35 * scale))
	}
	slope := Clamp01(math.Abs(TheilSenSlope(normalized)) * 4)

	return []Vote{
		{Exhibit: "cusum", Score: CUSUMScore(normalized, 0.02)},
		{Exhibit: "page-hinkley", Score: PageHinkleyScore(normalized, 0.04, 1.25)},
		{Exhibit: "adwin", Score: ADWINScore(normalized, 0.01, 3)},
		{Exhibit: "bocpd-beta", Score: bocpd},
		{Exhibit: "robust-jump", Score: jump},
		{Exhibit: "theil-sen", Score: slope},
	}
}
