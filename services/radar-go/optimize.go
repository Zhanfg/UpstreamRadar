package radar

import (
	"sort"
)

type Item struct {
	Name string
	Cost int
	Utility float64
	Novelty float64
	Risk float64
	Tags []string
	Ecosystem string
}

func itemsFromCandidates(candidates []Candidate) []Item {
	items:=make([]Item,len(candidates))
	for i,candidate:=range candidates {
		items[i]=Item{
			Name:candidate.Name,
			Cost:candidate.Cost,
			Utility:candidate.Utility,
			Novelty:candidate.StructuralNovelty,
			Risk:candidate.TailRisk,
			Tags:append([]string{},candidate.Tags...),
			Ecosystem:candidate.Ecosystem,
		}
	}
	return items
}

func ExactKnapsack(items []Item,budget int) []string {
	if budget<=0 || len(items)==0 { return nil }
	type state struct { utility float64; names []string }
	dp:=make([]state,budget+1)
	for _,item:=range items {
		if item.Cost<=0 { panic("item cost must be positive") }
		if item.Cost>budget { continue }
		for capacity:=budget;capacity>=item.Cost;capacity-- {
			previous:=dp[capacity-item.Cost]
			names:=append([]string{},previous.names...)
			names=append(names,item.Name)
			sort.Strings(names)
			candidateUtility:=previous.utility+item.Utility
			current:=dp[capacity]
			if candidateUtility>current.utility+1e-12 ||
				(abs(candidateUtility-current.utility)<=1e-12 && lexicalLess(names,current.names)) {
				dp[capacity]=state{utility:candidateUtility,names:names}
			}
		}
	}
	best:=state{}
	for _,candidate:=range dp {
		if candidate.utility>best.utility+1e-12 ||
			(abs(candidate.utility-best.utility)<=1e-12 && lexicalLess(candidate.names,best.names)) {
			best=candidate
		}
	}
	return best.names
}

func lexicalLess(left,right []string) bool {
	if len(right)==0 && len(left)>0 { return true }
	size:=len(left); if len(right)<size { size=len(right) }
	for i:=0;i<size;i++ {
		if left[i]<right[i] { return true }
		if left[i]>right[i] { return false }
	}
	return len(left)<len(right)
}

func EpsilonPareto(items []Item,epsilon float64) []string {
	if epsilon<0 { epsilon=0 }
	dominates:=func(left,right Item) bool {
		weak:=left.Utility+epsilon>=right.Utility &&
			left.Novelty+epsilon>=right.Novelty &&
			left.Risk<=right.Risk+epsilon
		strict:=left.Utility>right.Utility+epsilon ||
			left.Novelty>right.Novelty+epsilon ||
			left.Risk+epsilon<right.Risk
		return weak&&strict
	}
	frontier:=[]string{}
	for i,item:=range items {
		dominated:=false
		for j,other:=range items {
			if i!=j && dominates(other,item) { dominated=true;break }
		}
		if !dominated { frontier=append(frontier,item.Name) }
	}
	sort.Strings(frontier)
	return frontier
}

func CELFSelect(items []Item,budget int) []string {
	byName:=map[string]Item{}
	for _,item:=range items { byName[item.Name]=item }
	selected:=map[string]bool{}
	spent:=0
	type cached struct{ gain float64; stamp int }
	cache:=map[string]cached{}

	coveredTags:=func() map[string]bool {
		covered:=map[string]bool{}
		for name:=range selected {
			for _,tag:=range byName[name].Tags { covered[tag]=true }
		}
		return covered
	}
	marginal:=func(item Item) float64 {
		covered:=coveredTags()
		newTags:=0
		seen:=map[string]bool{}
		for _,tag:=range item.Tags {
			if seen[tag] { continue }
			seen[tag]=true
			if !covered[tag] { newTags++ }
		}
		return float64(newTags)+0.50*item.Utility+0.25*item.Novelty-0.15*item.Risk
	}
	for _,item:=range items { cache[item.Name]=cached{gain:marginal(item),stamp:0} }

	for len(cache)>0 {
		best:=""
		bestRatio:=-1e300
		bestGain:=-1e300
		for name,value:=range cache {
			cost:=float64(maxInt(byName[name].Cost,1))
			ratio:=value.gain/cost
			if ratio>bestRatio || (ratio==bestRatio && (value.gain>bestGain || (value.gain==bestGain && (best==""||name<best)))) {
				best,bestRatio,bestGain=name,ratio,value.gain
			}
		}
		value:=cache[best]
		if value.stamp!=len(selected) {
			cache[best]=cached{gain:marginal(byName[best]),stamp:len(selected)}
			continue
		}
		delete(cache,best)
		item:=byName[best]
		if spent+item.Cost>budget { continue }
		if value.gain<=0 { break }
		selected[best]=true
		spent+=item.Cost
	}
	out:=make([]string,0,len(selected))
	for name:=range selected { out=append(out,name) }
	sort.Strings(out)
	return out
}

func PortfolioUtility(selected []string,items []Item,coverageBonus,redundancyPenalty float64) float64 {
	byName:=map[string]Item{}
	for _,item:=range items { byName[item.Name]=item }
	total:=0.0
	counts:=map[string]int{}
	for _,name:=range selected {
		item,ok:=byName[name]; if !ok { continue }
		total+=item.Utility
		seen:=map[string]bool{}
		for _,tag:=range item.Tags {
			if seen[tag] { continue }
			seen[tag]=true
			counts[tag]++
		}
	}
	duplicates:=0
	for _,count:=range counts { if count>1 { duplicates+=count-1 } }
	return total+coverageBonus*float64(len(counts))-redundancyPenalty*float64(duplicates)
}

type beamState struct {
	selected []string
	spent int
	objective float64
	ecosystems map[string]int
}

func ConstrainedBeam(candidates []Candidate,budget,beamWidth,ecosystemCap int,coverageBonus,redundancyPenalty float64) ([]string,float64) {
	items:=itemsFromCandidates(candidates)
	byName:=map[string]Candidate{}
	for _,candidate:=range candidates { byName[candidate.Name]=candidate }
	ordered:=append([]Candidate{},candidates...)
	sort.Slice(ordered,func(i,j int) bool {
		left:=ordered[i].Utility/float64(maxInt(ordered[i].Cost,1))
		right:=ordered[j].Utility/float64(maxInt(ordered[j].Cost,1))
		if left==right { return ordered[i].Name<ordered[j].Name }
		return left>right
	})
	beam:=[]beamState{{selected:[]string{},ecosystems:map[string]int{}}}
	if beamWidth<8 { beamWidth=8 }

	for _,candidate:=range ordered {
		next:=append([]beamState{},beam...)
		for _,state:=range beam {
			if state.spent+candidate.Cost>budget { continue }
			if state.ecosystems[candidate.Ecosystem]>=ecosystemCap { continue }
			selected:=append([]string{},state.selected...)
			selected=append(selected,candidate.Name)
			sort.Strings(selected)
			ecosystems:=map[string]int{}
			for key,value:=range state.ecosystems { ecosystems[key]=value }
			ecosystems[candidate.Ecosystem]++
			objective:=PortfolioUtility(selected,items,coverageBonus,redundancyPenalty)
			next=append(next,beamState{selected:selected,spent:state.spent+candidate.Cost,objective:objective,ecosystems:ecosystems})
		}
		sort.Slice(next,func(i,j int) bool {
			if next[i].objective==next[j].objective {
				if next[i].spent==next[j].spent { return lexicalLess(next[i].selected,next[j].selected) }
				return next[i].spent<next[j].spent
			}
			return next[i].objective>next[j].objective
		})
		dedup:=make([]beamState,0,minInt(len(next),beamWidth))
		seen:=map[string]bool{}
		for _,state:=range next {
			key:=joinNames(state.selected)
			if seen[key] { continue }
			seen[key]=true
			dedup=append(dedup,state)
			if len(dedup)>=beamWidth { break }
		}
		beam=dedup
	}
	best:=beamState{}
	for _,state:=range beam {
		if state.objective>best.objective || (state.objective==best.objective && state.spent<best.spent) { best=state }
	}
	_ = byName
	return best.selected,best.objective
}

func joinNames(values []string) string {
	if len(values)==0 { return "" }
	total:=0
	for _,value:=range values { total+=len(value)+1 }
	buffer:=make([]byte,0,total)
	for _,value:=range values { buffer=append(buffer,value...);buffer=append(buffer,0) }
	return string(buffer)
}

func minInt(left,right int) int { if left<right { return left }; return right }
