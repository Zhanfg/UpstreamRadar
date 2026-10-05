package main

import (
	"math"
	"testing"
)

func almostEqual(a, b, eps float64) bool {
	return math.Abs(a-b) <= eps
}

func TestSurpriseOrdering(t *testing.T) {
	high := surprise(0.9, 0.2)
	low := surprise(0.21, 0.2)
	if !(high > low && high >= 0 && high <= 1) {
		t.Fatalf("unexpected surprise values high=%f low=%f", high, low)
	}
}

func TestCVaRTailSemantics(t *testing.T) {
	got := cvar([]float64{0.1, 0.2, 0.3, 0.9}, 0.75)
	if !almostEqual(got, 0.9, 1e-12) {
		t.Fatalf("cvar mismatch: got=%f want=0.9", got)
	}
	got = cvar([]float64{0.1, 0.2, 0.3, 0.4}, 0.5)
	if !almostEqual(got, 0.35, 1e-12) {
		t.Fatalf("cvar mismatch: got=%f want=0.35", got)
	}
}
