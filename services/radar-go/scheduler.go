package radar

import (
	"math"
	"sort"
)

type Scheduler struct {
	Config Config
}

func NewScheduler(config Config) (*Scheduler,error) {
	if err:=config.Validate();err!=nil { return nil,err }
	return &Scheduler{Config:config},nil
}

func DefaultScheduler() *Scheduler {
	scheduler,err:=NewScheduler(DefaultConfig())
	if err!=nil { panic(err) }
	return scheduler
}

func (s *Scheduler) empiricalBayesPriors(records []RepositorySignal) map[string][2]float64 {
	globalHits,globalMisses:=0,0
	type counts struct{ hits,misses int }
	byEcosystem:=map[string]counts{}
	for _,record:=range records {
		globalHits+=record.RecentChangeHits
		globalMisses+=record.RecentChangeMisses
		value:=byEcosystem[record.Ecosystem]
		value.hits+=record.RecentChangeHits
		value.misses+=record.RecentChangeMisses
		byEcosystem[record.Ecosystem]=value
	}
	globalRate:=(float64(globalHits)+1)/(float64(globalHits+globalMisses)+2)
	out:=map[string][2]float64{}
	strength:=s.Config.EmpiricalBayesStrength
	shrinkage:=s.Config.EmpiricalBayesShrinkage
	for ecosystem,value:=range byEcosystem {
		total:=value.hits+value.misses
		localRate:=(float64(value.hits)+1)/(float64(total)+2)
		sampleWeight:=float64(total)/(float64(total)+strength)
		blended:=sampleWeight*localRate+(1-sampleWeight)*globalRate
		rate:=(1-shrinkage)*blended+shrinkage*globalRate
		out[ecosystem]=[2]float64{
			math.Max(1e-9,1+strength*rate),
			math.Max(1e-9,1+strength*(1-rate)),
		}
	}
	return out
}

func changeProbability(record RepositorySignal,prior [2]float64) (float64,float64) {
	alpha:=prior[0]+float64(record.RecentChangeHits)
	beta:=prior[1]+float64(record.RecentChangeMisses)
	total:=alpha+beta
	probability:=alpha/math.Max(total,1e-12)
	variance:=alpha*beta/math.Max(total*total*(total+1),1e-12)
	return Clamp01(probability),math.Sqrt(math.Max(0,variance))
}

func field(record RepositorySignal,index int) float64 {
	switch index {
	case 0:return record.CommitVelocity
	case 1:return record.ReleaseVelocity
	case 2:return record.IssueVelocity
	case 3:return record.ContributorVelocity
	case 4:return record.MaintainerActivity
	case 5:return record.SecuritySignal
	case 6:return record.BreakageRisk
	case 7:return record.DependencyImportance
	case 8:return record.Novelty
	case 9:return record.DownstreamRelevance
	default:return 0
	}
}

func normalizedLocal(record RepositorySignal,population []RepositorySignal) []float64 {
	out:=make([]float64,10)
	for index:=0;index<10;index++ {
		column:=make([]float64,len(population))
		for i,candidate:=range population { column[i]=field(candidate,index) }
		center:=Median(column)
		scale:=MAD(column,&center)
		out[index]=StableSigmoid((field(record,index)-center)/math.Max(scale,1e-9))
	}
	return out
}

func reliability(record RepositorySignal) float64 {
	base:=Clamp01(record.SourceReliability)
	if base==0 { base=1 }
	decay:=math.Exp(-0.22*float64(record.FailureStreak))
	return Clamp01(math.Max(0.05,base*decay))
}

func (s *Scheduler) tailRisk(record RepositorySignal) float64 {
	impacts:=make([]float64,len(record.ImpactHistory))
	for i,value:=range record.ImpactHistory { impacts[i]=Clamp01(value/10) }
	cvar:=CVaR(impacts,s.Config.CVaRQuantile)
	security:=Clamp01(record.SecuritySignal/10)
	breakage:=Clamp01(record.BreakageRisk/10)
	failure:=1-math.Exp(-0.28*float64(record.FailureStreak))
	return Clamp01(0.46*cvar+0.24*security+0.18*breakage+0.12*failure)
}

func surprise(record RepositorySignal,predicted float64) float64 {
	empirical:=0.5
	if len(record.ChangeHistory)>0 {
		start:=0
		if len(record.ChangeHistory)>12 { start=len(record.ChangeHistory)-12 }
		hits:=0
		for _,value:=range record.ChangeHistory[start:] { if value!=0 { hits++ } }
		empirical=(float64(hits)+0.5)/(float64(len(record.ChangeHistory[start:]))+1)
	} else {
		total:=record.RecentChangeHits+record.RecentChangeMisses
		empirical=(float64(record.RecentChangeHits)+0.5)/(float64(total)+1)
	}
	return Clamp01(1-math.Exp(-3.4*BernoulliKL(empirical,predicted)))
}

func robustGallery(features []float64) Gallery {
	huber:=StableSigmoid(HuberLocation(features,1.345,16))
	trimmed:=StableSigmoid(TrimmedMean(features,0.10))
	hampel:=1-HampelOutlierFraction(features,3)
	slope:=Clamp01(math.Abs(TheilSenSlope(features)))
	return NewGallery("robust-statistics",[]Vote{
		{Exhibit:"huber",Score:Clamp01(huber)},
		{Exhibit:"trimmed-mean",Score:Clamp01(trimmed)},
		{Exhibit:"hampel-cleanliness",Score:Clamp01(hampel)},
		{Exhibit:"theil-sen",Score:slope},
	})
}

func changeGallery(record RepositorySignal) Gallery {
	return NewGallery("change-detection",ChangeVotes(record.ImpactHistory,record.ChangeHistory))
}

func informationGallery(record RepositorySignal) Gallery {
	values:=make([]float64,len(record.ImpactHistory))
	for i,value:=range record.ImpactHistory { values[i]=Clamp01(value/10) }
	return NewGallery("information-distance",DistributionShiftVotes(values))
}

func explorationGallery(record RepositorySignal,totalObservations int) Gallery {
	values:=make([]float64,len(record.ImpactHistory))
	for i,value:=range record.ImpactHistory { values[i]=Clamp01(value/10) }
	variance:=WinsorizedVariance(values,3.5)
	return NewGallery("online-learning",ExplorationVotes(
		record.RecentChangeHits,
		record.RecentChangeMisses,
		record.Observations(),
		variance,
		totalObservations,
	))
}

func sketchesGallery(record RepositorySignal,peers [][]string) Gallery {
	dependencies:=record.NormalizedDependencies()
	novelty:=DependencyNovelty(dependencies,peers,64)
	exactSimilarity:=0.0
	if len(peers)>0 {
		for _,peer:=range peers { exactSimilarity+=ExactJaccard(dependencies,peer) }
		exactSimilarity/=float64(len(peers))
	}
	return NewGallery("streaming-sketch",[]Vote{
		{Exhibit:"minhash-novelty",Score:novelty},
		{Exhibit:"exact-jaccard-novelty",Score:Clamp01(1-exactSimilarity)},
	})
}

func reasons(candidate Candidate) []string {
	out:=[]string{}
	if candidate.ChangeProbability>=0.65 { out=append(out,"likely-change") }
	if candidate.Museum.Change.Consensus>=0.55 { out=append(out,"change-consensus") }
	if candidate.Museum.Information.Consensus>=0.45 { out=append(out,"information-shift") }
	if candidate.GraphInfluence>=0.55 { out=append(out,"dependency-hub") }
	if candidate.StructuralNovelty>=0.55 { out=append(out,"structural-novelty") }
	if candidate.TailRisk>=0.70 { out=append(out,"tail-risk") }
	if candidate.Museum.Consensus>=0.62 { out=append(out,"museum-consensus") }
	if candidate.Museum.Disagreement>=0.45 { out=append(out,"algorithm-disagreement") }
	return out
}

func uniqueSorted(values []string) []string {
	seen:=map[string]bool{}
	out:=[]string{}
	for _,value:=range values {
		if value=="" || seen[value] { continue }
		seen[value]=true
		out=append(out,value)
	}
	sort.Strings(out)
	return out
}

func (s *Scheduler) Score(records []RepositorySignal) ([]Candidate,error) {
	if len(records)==0 { return []Candidate{},nil }
	for _,record:=range records { if err:=record.Validate();err!=nil { return nil,err } }

	priors:=s.empiricalBayesPriors(records)
	totalObservations:=1
	for _,record:=range records { totalObservations+=record.Observations() }

	type preliminary struct {
		probability float64
		uncertainty float64
		features []float64
		local float64
		surprise float64
	}
	pre:=map[string]preliminary{}
	seeds:=map[string]float64{}
	for _,record:=range records {
		prior,ok:=priors[record.Ecosystem]
		if !ok { prior=[2]float64{1,1} }
		probability,uncertainty:=changeProbability(record,prior)
		features:=normalizedLocal(record,records)
		local:=Clamp01(StableSigmoid(HuberLocation(features,1.345,16))*(1-0.12*HampelOutlierFraction(features,3)))
		sp:=surprise(record,probability)
		pre[record.Name]=preliminary{probability:probability,uncertainty:uncertainty,features:features,local:local,surprise:sp}
		seeds[record.Name]=Clamp01(0.45*probability+0.35*local+0.20*sp)
	}

	graph:=GraphFromSignals(records)
	graphGalleries:=GraphGallery(graph,seeds)
	dependencySets:=map[string][]string{}
	for _,record:=range records { dependencySets[record.Name]=record.NormalizedDependencies() }

	candidates:=make([]Candidate,0,len(records))
	for _,record:=range records {
		p:=pre[record.Name]
		peers:=[][]string{}
		for _,other:=range records {
			if other.Name!=record.Name { peers=append(peers,dependencySets[other.Name]) }
		}
		graphGallery,ok:=graphGalleries[record.Name]
		if !ok { graphGallery=NewGallery("graph",nil) }
		museum:=NewMuseum(
			robustGallery(p.features),
			changeGallery(record),
			informationGallery(record),
			graphGallery,
			explorationGallery(record,totalObservations),
			sketchesGallery(record,peers),
		)
		structuralNovelty:=Clamp01(
			0.55*museum.Sketches.Consensus+
			0.25*Clamp01(record.Novelty/10)+
			0.20*museum.Information.Consensus,
		)
		tail:=s.tailRisk(record)
		trust:=reliability(record)
		freshness:=1-math.Exp(-math.Max(0,record.FreshnessHours)/48)
		security:=Clamp01(record.SecuritySignal/10)
		dependency:=Clamp01(record.DependencyImportance/10)
		downstream:=Clamp01(record.DownstreamRelevance/10)

		base:=(
			0.16*p.probability+
			0.11*p.local+
			0.10*museum.Graph.Consensus+
			0.08*structuralNovelty+
			0.08*p.surprise+
			0.08*museum.Change.Consensus+
			0.07*museum.Information.Consensus+
			0.07*museum.Exploration.Consensus+
			0.06*security+
			0.05*dependency+
			0.04*downstream+
			0.04*freshness+
			s.Config.MuseumWeight*museum.Consensus)/
			(0.94+s.Config.MuseumWeight)

		base*=1-s.Config.MuseumDisagreementPenalty*museum.Disagreement
		riskAdjusted:=base*(1-s.Config.TailRiskPenalty*tail)*(0.82+0.18*trust)
		utility:=riskAdjusted*(1+0.04*math.Min(p.uncertainty,1))*(1+0.05/float64(record.EffectiveCost()))

		tags:=append([]string{},record.Tags...)
		tags=append(tags,record.Ecosystem)
		tags=append(tags,record.NormalizedDependencies()...)

		candidate:=Candidate{
			Name:record.Name,
			Ecosystem:record.Ecosystem,
			Cost:record.EffectiveCost(),
			ChangeProbability:p.probability,
			Uncertainty:p.uncertainty,
			LocalSignal:p.local,
			GraphInfluence:museum.Graph.Consensus,
			StructuralNovelty:structuralNovelty,
			TailRisk:tail,
			Reliability:trust,
			Exploration:museum.Exploration.Consensus,
			RiskAdjusted:riskAdjusted,
			Utility:utility,
			Museum:museum,
			Tags:uniqueSorted(tags),
		}
		candidate.Reasons=reasons(candidate)
		candidate.Tags=uniqueSorted(append(candidate.Tags,candidate.Reasons...))
		candidates=append(candidates,candidate)
	}
	sort.Slice(candidates,func(i,j int) bool {
		if candidates[i].Utility==candidates[j].Utility { return candidates[i].Name<candidates[j].Name }
		return candidates[i].Utility>candidates[j].Utility
	})
	return candidates,nil
}

func (s *Scheduler) Schedule(records []RepositorySignal,budget int) (Schedule,error) {
	candidates,err:=s.Score(records)
	if err!=nil { return Schedule{},err }
	selectedNames,objective:=ConstrainedBeam(
		candidates,budget,s.Config.BeamWidth,s.Config.EcosystemCap,
		s.Config.CoverageBonus,s.Config.RedundancyPenalty,
	)
	byName:=map[string]Candidate{}
	for _,candidate:=range candidates { byName[candidate.Name]=candidate }
	selected:=make([]Candidate,0,len(selectedNames))
	spent:=0
	for _,name:=range selectedNames {
		if candidate,ok:=byName[name];ok { selected=append(selected,candidate);spent+=candidate.Cost }
	}
	items:=itemsFromCandidates(candidates)
	exact:=ExactKnapsack(items,budget)
	celf:=CELFSelect(items,budget)
	pareto:=EpsilonPareto(items,1e-6)
	productionUtility,exactUtility:=0.0,0.0
	for _,candidate:=range selected { productionUtility+=candidate.Utility }
	for _,name:=range exact { if candidate,ok:=byName[name];ok { exactUtility+=candidate.Utility } }
	ratio:=1.0
	if exactUtility>0 { ratio=math.Min(1,productionUtility/exactUtility) }

	audit:=map[string]any{
		"production":selectedNames,
		"exact_knapsack":exact,
		"celf":celf,
		"pareto":pareto,
		"base_utility_ratio":ratio,
	}
	return Schedule{Selected:selected,Budget:budget,Spent:spent,Objective:objective,Audit:audit},nil
}
