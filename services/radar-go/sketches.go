package radar

import (
	"math"
	"sort"
)

func hash64(seed uint64, value string) uint64 {
	hash := uint64(0xcbf29ce484222325) ^ seed*0x9e3779b97f4a7c15
	for i := 0; i < len(value); i++ {
		hash ^= uint64(value[i])
		hash *= 0x100000001b3
		hash ^= hash >> 32
	}
	return hash
}

func MinHashSignature(values []string, permutations int) []uint64 {
	if permutations < 1 {
		permutations = 1
	}
	unique := map[string]struct{}{}
	for _, value := range values {
		if value != "" {
			unique[value] = struct{}{}
		}
	}
	if len(unique) == 0 {
		return nil
	}
	signature := make([]uint64, permutations)
	for seed := 0; seed < permutations; seed++ {
		minimum := ^uint64(0)
		for value := range unique {
			hashed := hash64(uint64(seed), value)
			if hashed < minimum {
				minimum = hashed
			}
		}
		signature[seed] = minimum
	}
	return signature
}

func MinHashSimilarity(left, right []uint64) float64 {
	if len(left) == 0 && len(right) == 0 {
		return 1
	}
	if len(left) == 0 || len(right) == 0 {
		return 0
	}
	size := len(left)
	if len(right) < size {
		size = len(right)
	}
	equal := 0
	for i := 0; i < size; i++ {
		if left[i] == right[i] {
			equal++
		}
	}
	return float64(equal) / float64(size)
}

func ExactJaccard(left, right []string) float64 {
	a, b := map[string]struct{}{}, map[string]struct{}{}
	for _, value := range left { a[value]=struct{}{} }
	for _, value := range right { b[value]=struct{}{} }
	if len(a)==0 && len(b)==0 { return 1 }
	intersection:=0
	union:=map[string]struct{}{}
	for value:=range a { union[value]=struct{}{}; if _,ok:=b[value];ok { intersection++ } }
	for value:=range b { union[value]=struct{}{} }
	return float64(intersection)/float64(maxInt(len(union),1))
}

func DependencyNovelty(target []string, peers [][]string, permutations int) float64 {
	signature:=MinHashSignature(target,permutations)
	if len(signature)==0 { return 0 }
	maximum:=0.0
	for _,peer:=range peers {
		other:=MinHashSignature(peer,permutations)
		if len(other)==0 { continue }
		similarity:=MinHashSimilarity(signature,other)
		if similarity>maximum { maximum=similarity }
	}
	return Clamp01(1-maximum)
}

type BloomFilter struct {
	bits int
	hashes int
	bitmap []byte
	count int
}

func NewBloomFilter(bits,hashes int) *BloomFilter {
	if bits<=0 || hashes<=0 { panic("bits and hashes must be positive") }
	return &BloomFilter{bits:bits,hashes:hashes,bitmap:make([]byte,(bits+7)/8)}
}

func (f *BloomFilter) Add(value string) {
	for seed:=0;seed<f.hashes;seed++ {
		position:=int(hash64(uint64(seed),value)%uint64(f.bits))
		f.bitmap[position/8] |= 1<<uint(position%8)
	}
	f.count++
}

func (f *BloomFilter) Contains(value string) bool {
	for seed:=0;seed<f.hashes;seed++ {
		position:=int(hash64(uint64(seed),value)%uint64(f.bits))
		if f.bitmap[position/8]&(1<<uint(position%8))==0 { return false }
	}
	return true
}

func (f *BloomFilter) EstimatedFalsePositiveRate() float64 {
	return math.Pow(1-math.Exp(-float64(f.hashes*f.count)/float64(f.bits)),float64(f.hashes))
}

type CountMinSketch struct {
	width int
	depth int
	table [][]uint64
}

func NewCountMinSketch(width,depth int) *CountMinSketch {
	if width<=0 || depth<=0 { panic("width and depth must be positive") }
	table:=make([][]uint64,depth)
	for i:=range table { table[i]=make([]uint64,width) }
	return &CountMinSketch{width:width,depth:depth,table:table}
}

func (s *CountMinSketch) Add(key string,count uint64) {
	for seed:=0;seed<s.depth;seed++ {
		index:=int(hash64(uint64(seed),key)%uint64(s.width))
		if ^uint64(0)-s.table[seed][index] < count {
			s.table[seed][index]=^uint64(0)
		} else {
			s.table[seed][index]+=count
		}
	}
}

func (s *CountMinSketch) Estimate(key string) uint64 {
	minimum:=^uint64(0)
	for seed:=0;seed<s.depth;seed++ {
		index:=int(hash64(uint64(seed),key)%uint64(s.width))
		if s.table[seed][index]<minimum { minimum=s.table[seed][index] }
	}
	if minimum==^uint64(0) && s.depth==0 { return 0 }
	return minimum
}

func (s *CountMinSketch) Merge(other *CountMinSketch) error {
	if s.width!=other.width || s.depth!=other.depth { return errDimensions }
	for row:=0;row<s.depth;row++ {
		for col:=0;col<s.width;col++ {
			value:=other.table[row][col]
			if ^uint64(0)-s.table[row][col] < value {
				s.table[row][col]=^uint64(0)
			} else {
				s.table[row][col]+=value
			}
		}
	}
	return nil
}

type sketchError string
func (e sketchError) Error() string { return string(e) }
const errDimensions sketchError = "sketch dimensions must match"

type HyperLogLog struct {
	precision uint8
	registers []uint8
}

func NewHyperLogLog(precision uint8) *HyperLogLog {
	if precision<4 || precision>16 { panic("precision must be in [4,16]") }
	return &HyperLogLog{precision:precision,registers:make([]uint8,1<<precision)}
}

func (h *HyperLogLog) Add(value string) {
	hashed:=hash64(0x484c4c,value)
	indexMask:=uint64((1<<h.precision)-1)
	index:=int(hashed&indexMask)
	remainder:=hashed>>h.precision
	width:=64-int(h.precision)
	rank:=width+1
	if remainder!=0 {
		leading:=bitsLeadingZeros64(remainder)-int(h.precision)
		rank=leading+1
	}
	if rank<1 { rank=1 }
	if rank>255 { rank=255 }
	if uint8(rank)>h.registers[index] { h.registers[index]=uint8(rank) }
}

func bitsLeadingZeros64(value uint64) int {
	if value==0 { return 64 }
	count:=0
	mask:=uint64(1)<<63
	for value&mask==0 { count++; mask>>=1 }
	return count
}

func (h *HyperLogLog) Estimate() float64 {
	m:=float64(len(h.registers))
	alpha:=0.7213/(1+1.079/m)
	switch len(h.registers) {
	case 16: alpha=0.673
	case 32: alpha=0.697
	case 64: alpha=0.709
	}
	harmonic:=0.0
	zeros:=0
	for _,register:=range h.registers {
		harmonic += math.Pow(2,-float64(register))
		if register==0 { zeros++ }
	}
	estimate:=alpha*m*m/math.Max(harmonic,1e-12)
	if estimate<=2.5*m && zeros>0 { estimate=m*math.Log(m/float64(zeros)) }
	return estimate
}

type HeavyHitter struct {
	Key string `json:"key"`
	Estimate uint64 `json:"estimate"`
	Error uint64 `json:"error"`
}

type SpaceSaving struct {
	capacity int
	counters map[string][2]uint64
}

func NewSpaceSaving(capacity int) *SpaceSaving {
	if capacity<=0 { panic("capacity must be positive") }
	return &SpaceSaving{capacity:capacity,counters:map[string][2]uint64{}}
}

func (s *SpaceSaving) Add(key string,count uint64) {
	if count==0 { panic("count must be positive") }
	if current,ok:=s.counters[key];ok {
		current[0]+=count
		s.counters[key]=current
		return
	}
	if len(s.counters)<s.capacity {
		s.counters[key]=[2]uint64{count,0}
		return
	}
	victim:=""
	minimum:=^uint64(0)
	for candidate,value:=range s.counters {
		if value[0]<minimum || (value[0]==minimum && (victim=="" || candidate<victim)) {
			victim=candidate; minimum=value[0]
		}
	}
	delete(s.counters,victim)
	s.counters[key]=[2]uint64{minimum+count,minimum}
}

func (s *SpaceSaving) HeavyHitters() []HeavyHitter {
	out:=make([]HeavyHitter,0,len(s.counters))
	for key,value:=range s.counters {
		out=append(out,HeavyHitter{Key:key,Estimate:value[0],Error:value[1]})
	}
	sort.Slice(out,func(i,j int) bool {
		if out[i].Estimate==out[j].Estimate { return out[i].Key<out[j].Key }
		return out[i].Estimate>out[j].Estimate
	})
	return out
}
