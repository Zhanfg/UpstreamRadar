package radar

import (
	"encoding/json"
	"errors"
	"math"
	"sort"
	"strings"
)

type RepositorySignal struct {
	Name                 string   `json:"name"`
	Ecosystem            string   `json:"ecosystem"`
	Cost                 int      `json:"cost"`
	FreshnessHours       float64  `json:"freshness_hours"`
	CommitVelocity       float64  `json:"commit_velocity"`
	ReleaseVelocity      float64  `json:"release_velocity"`
	IssueVelocity        float64  `json:"issue_velocity"`
	ContributorVelocity  float64  `json:"contributor_velocity"`
	MaintainerActivity   float64  `json:"maintainer_activity"`
	SecuritySignal       float64  `json:"security_signal"`
	BreakageRisk         float64  `json:"breakage_risk"`
	DependencyImportance float64  `json:"dependency_importance"`
	Novelty              float64  `json:"novelty"`
	DownstreamRelevance  float64  `json:"downstream_relevance"`
	RecentChangeHits     int      `json:"recent_change_hits"`
	RecentChangeMisses   int      `json:"recent_change_misses"`
	ObservationCount     int      `json:"observation_count"`
	FailureStreak        int      `json:"failure_streak"`
	SourceReliability    float64  `json:"source_reliability"`
	ChangeHistory        []int    `json:"change_history"`
	ImpactHistory        []float64 `json:"impact_history"`
	Dependencies         []string `json:"dependencies"`
	Tags                 []string `json:"tags"`
}

func (s RepositorySignal) Validate() error {
	if strings.TrimSpace(s.Name) == "" {
		return errors.New("name must not be empty")
	}
	if s.Cost < 0 {
		return errors.New("cost must be non-negative")
	}
	if s.RecentChangeHits < 0 || s.RecentChangeMisses < 0 || s.ObservationCount < 0 {
		return errors.New("counts must be non-negative")
	}
	return nil
}

func (s RepositorySignal) EffectiveCost() int {
	if s.Cost <= 0 {
		return 1
	}
	return s.Cost
}

func (s RepositorySignal) Observations() int {
	total := s.RecentChangeHits + s.RecentChangeMisses
	if s.ObservationCount > total {
		return s.ObservationCount
	}
	return total
}

func (s RepositorySignal) NormalizedDependencies() []string {
	seen := map[string]struct{}{}
	out := make([]string, 0, len(s.Dependencies))
	for _, raw := range s.Dependencies {
		value := strings.TrimSpace(raw)
		if value == "" || value == s.Name {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

type Vote struct {
	Exhibit string  `json:"exhibit"`
	Score   float64 `json:"score"`
}

type Gallery struct {
	Family       string  `json:"family"`
	Consensus    float64 `json:"consensus"`
	Disagreement float64 `json:"disagreement"`
	Votes        []Vote  `json:"votes"`
}

func NewGallery(family string, votes []Vote) Gallery {
	if len(votes) == 0 {
		return Gallery{Family: family, Votes: []Vote{}}
	}
	mean := 0.0
	for _, vote := range votes {
		mean += vote.Score
	}
	mean /= float64(len(votes))
	variance := 0.0
	for _, vote := range votes {
		delta := vote.Score - mean
		variance += delta * delta
	}
	variance /= float64(len(votes))
	disagreement := Clamp01(math.Sqrt(variance) * 2)
	consensus := Clamp01(mean * (1 - 0.22*disagreement))
	return Gallery{
		Family:       family,
		Consensus:    consensus,
		Disagreement: disagreement,
		Votes:        votes,
	}
}

type MuseumEvidence struct {
	Robust      Gallery `json:"robust"`
	Change      Gallery `json:"change"`
	Information Gallery `json:"information"`
	Graph       Gallery `json:"graph"`
	Exploration Gallery `json:"exploration"`
	Sketches    Gallery `json:"sketches"`

	Consensus    float64 `json:"consensus"`
	Disagreement float64 `json:"disagreement"`
}

func NewMuseum(galleries ...Gallery) MuseumEvidence {
	if len(galleries) != 6 {
		panic("NewMuseum requires six galleries")
	}
	mean := 0.0
	for _, gallery := range galleries {
		mean += gallery.Consensus
	}
	mean /= float64(len(galleries))
	variance := 0.0
	for _, gallery := range galleries {
		delta := gallery.Consensus - mean
		variance += delta * delta
	}
	variance /= float64(len(galleries))
	disagreement := Clamp01(math.Sqrt(variance) * 2)
	consensus := Clamp01(mean * (1 - 0.24*disagreement))
	return MuseumEvidence{
		Robust:       galleries[0],
		Change:       galleries[1],
		Information:  galleries[2],
		Graph:        galleries[3],
		Exploration:  galleries[4],
		Sketches:     galleries[5],
		Consensus:    consensus,
		Disagreement: disagreement,
	}
}

type Candidate struct {
	Name              string         `json:"name"`
	Ecosystem         string         `json:"ecosystem"`
	Cost              int            `json:"cost"`
	ChangeProbability float64        `json:"change_probability"`
	Uncertainty       float64        `json:"uncertainty"`
	LocalSignal       float64        `json:"local_signal"`
	GraphInfluence    float64        `json:"graph_influence"`
	StructuralNovelty float64        `json:"structural_novelty"`
	TailRisk          float64        `json:"tail_risk"`
	Reliability       float64        `json:"reliability"`
	Exploration       float64        `json:"exploration"`
	RiskAdjusted      float64        `json:"risk_adjusted_utility"`
	Utility           float64        `json:"utility"`
	Museum            MuseumEvidence `json:"museum"`
	Reasons           []string       `json:"reasons"`
	Tags              []string       `json:"tags"`
}

type Schedule struct {
	Selected  []Candidate    `json:"selected"`
	Budget    int            `json:"budget"`
	Spent     int            `json:"spent"`
	Objective float64        `json:"objective"`
	Audit     map[string]any `json:"audit"`
}

type Config struct {
	EmpiricalBayesStrength     float64 `json:"empirical_bayes_strength"`
	EmpiricalBayesShrinkage    float64 `json:"empirical_bayes_shrinkage"`
	CVaRQuantile               float64 `json:"cvar_quantile"`
	TailRiskPenalty            float64 `json:"tail_risk_penalty"`
	MuseumWeight               float64 `json:"museum_weight"`
	MuseumDisagreementPenalty  float64 `json:"museum_disagreement_penalty"`
	EcosystemCap               int     `json:"ecosystem_cap"`
	BeamWidth                  int     `json:"beam_width"`
	CoverageBonus              float64 `json:"coverage_bonus"`
	RedundancyPenalty          float64 `json:"redundancy_penalty"`
}

func DefaultConfig() Config {
	return Config{
		EmpiricalBayesStrength:    4.0,
		EmpiricalBayesShrinkage:   0.35,
		CVaRQuantile:              0.75,
		TailRiskPenalty:           0.11,
		MuseumWeight:              0.12,
		MuseumDisagreementPenalty: 0.08,
		EcosystemCap:              3,
		BeamWidth:                 128,
		CoverageBonus:             0.08,
		RedundancyPenalty:         0.10,
	}
}

func (c Config) Validate() error {
	if c.EmpiricalBayesStrength <= 0 {
		return errors.New("empirical_bayes_strength must be positive")
	}
	if c.EmpiricalBayesShrinkage < 0 || c.EmpiricalBayesShrinkage > 1 {
		return errors.New("empirical_bayes_shrinkage must be in [0,1]")
	}
	if c.CVaRQuantile < 0.5 || c.CVaRQuantile >= 1 {
		return errors.New("cvar_quantile must be in [0.5,1)")
	}
	if c.EcosystemCap <= 0 || c.BeamWidth < 8 {
		return errors.New("ecosystem_cap must be positive and beam_width >= 8")
	}
	return nil
}

func DecodeSignals(data []byte) ([]RepositorySignal, error) {
	var signals []RepositorySignal
	if err := json.Unmarshal(data, &signals); err != nil {
		return nil, err
	}
	for i := range signals {
		if err := signals[i].Validate(); err != nil {
			return nil, err
		}
	}
	return signals, nil
}
