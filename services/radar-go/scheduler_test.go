package radar

import (
	"math"
	"reflect"
	"testing"
)

func testSignal(name,ecosystem string,cost int) RepositorySignal {
	return RepositorySignal{
		Name:name,Ecosystem:ecosystem,Cost:cost,
		FreshnessHours:2,
		CommitVelocity:5,ReleaseVelocity:2,IssueVelocity:3,
		ContributorVelocity:2,MaintainerActivity:6,
		SecuritySignal:4,BreakageRisk:3,DependencyImportance:6,
		Novelty:6,DownstreamRelevance:5,
		RecentChangeHits:4,RecentChangeMisses:4,ObservationCount:24,
		SourceReliability:0.95,
		ChangeHistory:[]int{0,0,0,1,0,1,1,1},
		ImpactHistory:[]float64{1,1,2,2,4,6,7,8},
	}
}

func TestSchedulerDeterministic(t *testing.T) {
	a:=testSignal("a","kernel",2)
	a.Dependencies=[]string{"hub"}
	b:=testSignal("b","app",1)
	b.RecentChangeHits=1;b.RecentChangeMisses=9
	hub:=testSignal("hub","kernel",2)
	records:=[]RepositorySignal{a,b,hub}
	s:=DefaultScheduler()
	first,err:=s.Schedule(records,3);if err!=nil { t.Fatal(err) }
	second,err:=s.Schedule(records,3);if err!=nil { t.Fatal(err) }
	if !reflect.DeepEqual(first,second) { t.Fatalf("schedule is not deterministic") }
	if first.Spent>3 || len(first.Selected)==0 { t.Fatalf("invalid schedule: %+v",first) }
}

func TestMuseumEvidenceBounded(t *testing.T) {
	records:=[]RepositorySignal{testSignal("a","x",1),testSignal("b","y",1)}
	records[0].Dependencies=[]string{"b"}
	scores,err:=DefaultScheduler().Score(records);if err!=nil { t.Fatal(err) }
	for _,candidate:=range scores {
		values:=[]float64{
			candidate.Museum.Consensus,candidate.Museum.Disagreement,
			candidate.Museum.Robust.Consensus,candidate.Museum.Change.Consensus,
			candidate.Museum.Information.Consensus,candidate.Museum.Graph.Consensus,
			candidate.Museum.Exploration.Consensus,candidate.Museum.Sketches.Consensus,
		}
		for _,value:=range values {
			if value<0 || value>1 || math.IsNaN(value) { t.Fatalf("unbounded museum value %v",value) }
		}
	}
}

func TestChangeDetectors(t *testing.T) {
	stable:=make([]float64,48)
	shifted:=make([]float64,48)
	for i:=range stable { stable[i]=0.1; if i<24 { shifted[i]=0.1 } else { shifted[i]=0.9 } }
	if CUSUMScore(shifted,0.02)<=CUSUMScore(stable,0.02) { t.Fatal("CUSUM did not detect shift") }
	if ADWINScore(shifted,0.01,3)<=ADWINScore(stable,0.01,3) { t.Fatal("ADWIN did not detect shift") }
}

func TestInformationDistances(t *testing.T) {
	left:=[]float64{0,0.1,0.2}
	right:=[]float64{0.8,0.9,1}
	if Wasserstein1D(left,right)<=0.6 { t.Fatal("Wasserstein too small") }
	if MaximumMeanDiscrepancy(left,right,0)<=0.3 { t.Fatal("MMD too small") }
	if math.Abs(JensenShannon([]float64{9,1,0,0},[]float64{0,0,1,9})-
		JensenShannon([]float64{0,0,1,9},[]float64{9,1,0,0}))>1e-12 {
		t.Fatal("JSD not symmetric")
	}
}

func TestSketches(t *testing.T) {
	filter:=NewBloomFilter(2048,5)
	for _,value:=range []string{"a","b","c"} { filter.Add(value) }
	for _,value:=range []string{"a","b","c"} { if !filter.Contains(value) { t.Fatalf("false negative %s",value) } }

	cms:=NewCountMinSketch(128,5)
	for i:=0;i<20;i++ { cms.Add("hot",1) }
	if cms.Estimate("hot")<20 { t.Fatal("count-min underestimated") }

	hll:=NewHyperLogLog(10)
	for i:=0;i<1000;i++ { hll.Add(fmtInt(i)) }
	estimate:=hll.Estimate()
	if math.Abs(estimate-1000)/1000>0.30 { t.Fatalf("HLL estimate %f",estimate) }
}

func fmtInt(value int) string {
	if value==0 { return "0" }
	digits:=[]byte{}
	for value>0 { digits=append(digits,byte('0'+value%10));value/=10 }
	for i,j:=0,len(digits)-1;i<j;i,j=i+1,j-1 { digits[i],digits[j]=digits[j],digits[i] }
	return string(digits)
}
