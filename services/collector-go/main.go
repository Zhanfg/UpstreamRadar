package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"sort"
)

type Event struct {
	Source    string  `json:"source"`
	EventType string  `json:"event_type"`
	Impact    float64 `json:"semantic_impact"`
}

type Bucket struct {
	Key         string        `json:"key"`
	Events      int           `json:"events"`
	TotalImpact float64       `json:"total_impact"`
	MeanImpact  float64       `json:"mean_impact"`
	Variance    float64       `json:"variance"`
	TailRisk    float64       `json:"tail_risk"`
	moments     OnlineMoments `json:"-"`
	impacts     []float64     `json:"-"`
}

func main() {
	scanner := bufio.NewScanner(os.Stdin)
	buckets := map[string]*Bucket{}
	for scanner.Scan() {
		var event Event
		if err := json.Unmarshal(scanner.Bytes(), &event); err != nil {
			fmt.Fprintln(os.Stderr, "invalid event:", err)
			os.Exit(2)
		}
		key := event.Source + "/" + event.EventType
		bucket := buckets[key]
		if bucket == nil {
			bucket = &Bucket{Key: key}
			buckets[key] = bucket
		}
		bucket.Events++
		bucket.TotalImpact += event.Impact
		bucket.moments.Push(event.Impact)
		bucket.impacts = append(bucket.impacts, event.Impact)
	}
	if err := scanner.Err(); err != nil {
		panic(err)
	}

	out := make([]Bucket, 0, len(buckets))
	for _, bucket := range buckets {
		bucket.MeanImpact = bucket.moments.Mean
		bucket.Variance = bucket.moments.Variance()
		normalized := make([]float64, 0, len(bucket.impacts))
		for _, impact := range bucket.impacts {
			normalized = append(normalized, impact/10.0)
		}
		bucket.TailRisk = cvar(normalized, 0.75)
		out = append(out, *bucket)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].TotalImpact == out[j].TotalImpact {
			return out[i].Key < out[j].Key
		}
		return out[i].TotalImpact > out[j].TotalImpact
	})
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(out); err != nil {
		panic(err)
	}
}
