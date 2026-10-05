package radar

import (
	"container/heap"
	"sort"
)

type Graph map[string][]string

func GraphFromSignals(signals []RepositorySignal) Graph {
	graph := Graph{}
	for _, signal := range signals {
		graph[signal.Name] = signal.NormalizedDependencies()
	}
	return graph
}

func graphNodes(graph Graph) []string {
	seen := map[string]struct{}{}
	for source, targets := range graph {
		seen[source] = struct{}{}
		for _, target := range targets {
			seen[target] = struct{}{}
		}
	}
	nodes := make([]string, 0, len(seen))
	for node := range seen {
		nodes = append(nodes, node)
	}
	sort.Strings(nodes)
	return nodes
}

func normalizedTargets(graph Graph, source string, known map[string]struct{}) []string {
	seen := map[string]struct{}{}
	out := make([]string, 0)
	for _, target := range graph[source] {
		if target == source {
			continue
		}
		if _, ok := known[target]; !ok {
			continue
		}
		if _, ok := seen[target]; ok {
			continue
		}
		seen[target] = struct{}{}
		out = append(out, target)
	}
	sort.Strings(out)
	return out
}

func PageRank(graph Graph, damping float64, steps int, seeds map[string]float64) map[string]float64 {
	nodes := graphNodes(graph)
	if len(nodes) == 0 {
		return map[string]float64{}
	}
	known := map[string]struct{}{}
	for _, node := range nodes {
		known[node] = struct{}{}
	}
	raw := map[string]float64{}
	total := 0.0
	for _, node := range nodes {
		value := 1.0
		if seed, ok := seeds[node]; ok && seed > 0 {
			value = seed
		}
		raw[node] = value
		total += value
	}
	teleport := map[string]float64{}
	rank := map[string]float64{}
	for _, node := range nodes {
		teleport[node] = raw[node] / total
		rank[node] = teleport[node]
	}
	if damping < 0 {
		damping = 0
	}
	if damping >= 1 {
		damping = 0.999999
	}
	if steps < 1 {
		steps = 1
	}

	for iteration := 0; iteration < steps; iteration++ {
		next := map[string]float64{}
		for _, node := range nodes {
			next[node] = (1 - damping) * teleport[node]
		}
		dangling := 0.0
		for _, source := range nodes {
			targets := normalizedTargets(graph, source, known)
			if len(targets) == 0 {
				dangling += rank[source]
				continue
			}
			share := damping * rank[source] / float64(len(targets))
			for _, target := range targets {
				next[target] += share
			}
		}
		if dangling > 0 {
			for _, node := range nodes {
				next[node] += damping * dangling * teleport[node]
			}
		}
		rank = next
	}
	scale := 0.0
	for _, value := range rank {
		scale += value
	}
	if scale <= 0 {
		scale = 1
	}
	for node := range rank {
		rank[node] /= scale
	}
	return rank
}

func HITS(graph Graph, steps int) (map[string]float64, map[string]float64) {
	nodes := graphNodes(graph)
	if len(nodes) == 0 {
		return map[string]float64{}, map[string]float64{}
	}
	known := map[string]struct{}{}
	for _, node := range nodes {
		known[node] = struct{}{}
	}
	incoming := map[string][]string{}
	outgoing := map[string][]string{}
	for _, node := range nodes {
		incoming[node] = []string{}
	}
	for _, source := range nodes {
		targets := normalizedTargets(graph, source, known)
		outgoing[source] = targets
		for _, target := range targets {
			incoming[target] = append(incoming[target], source)
		}
	}
	hubs, authorities := map[string]float64{}, map[string]float64{}
	for _, node := range nodes {
		hubs[node], authorities[node] = 1, 1
	}
	if steps < 1 {
		steps = 1
	}

	for iteration := 0; iteration < steps; iteration++ {
		nextAuth := map[string]float64{}
		norm := 0.0
		for _, node := range nodes {
			value := 0.0
			for _, source := range incoming[node] {
				value += hubs[source]
			}
			nextAuth[node] = value
			norm += value * value
		}
		norm = sqrtSafe(norm)
		for node := range nextAuth {
			nextAuth[node] /= norm
		}

		nextHubs := map[string]float64{}
		norm = 0
		for _, node := range nodes {
			value := 0.0
			for _, target := range outgoing[node] {
				value += nextAuth[target]
			}
			nextHubs[node] = value
			norm += value * value
		}
		norm = sqrtSafe(norm)
		for node := range nextHubs {
			nextHubs[node] /= norm
		}
		hubs, authorities = nextHubs, nextAuth
	}
	return hubs, authorities
}

func sqrtSafe(value float64) float64 {
	if value <= 1e-24 {
		return 1
	}
	return sqrt(value)
}

// local sqrt wrapper keeps graph.go self-contained and easy to benchmark.
func sqrt(value float64) float64 {
	x := value
	if x <= 0 {
		return 0
	}
	guess := x
	for i := 0; i < 24; i++ {
		next := 0.5 * (guess + x/guess)
		if abs(next-guess) <= 1e-14*maxFloat(1, abs(guess)) {
			return next
		}
		guess = next
	}
	return guess
}

func abs(value float64) float64 {
	if value < 0 {
		return -value
	}
	return value
}

func maxFloat(left, right float64) float64 {
	if left > right {
		return left
	}
	return right
}

func Katz(graph Graph, alpha float64, beta float64, steps int) map[string]float64 {
	nodes := graphNodes(graph)
	if len(nodes) == 0 {
		return map[string]float64{}
	}
	known := map[string]struct{}{}
	for _, node := range nodes {
		known[node] = struct{}{}
	}
	incoming := map[string][]string{}
	maxDegree := 1
	for _, node := range nodes {
		incoming[node] = []string{}
	}
	for _, source := range nodes {
		targets := normalizedTargets(graph, source, known)
		if len(targets) > maxDegree {
			maxDegree = len(targets)
		}
		for _, target := range targets {
			incoming[target] = append(incoming[target], source)
		}
	}
	if alpha <= 0 {
		alpha = 0.85 / float64(maxDegree)
	}
	if steps < 1 {
		steps = 1
	}
	scores := map[string]float64{}
	for _, node := range nodes {
		scores[node] = 1
	}
	for iteration := 0; iteration < steps; iteration++ {
		next := map[string]float64{}
		maximum := 0.0
		for _, node := range nodes {
			value := beta
			for _, source := range incoming[node] {
				value += alpha * scores[source]
			}
			next[node] = value
			if value > maximum {
				maximum = value
			}
		}
		if maximum <= 0 {
			maximum = 1
		}
		for node := range next {
			next[node] /= maximum
		}
		scores = next
	}
	return scores
}

func TarjanSCC(graph Graph) [][]string {
	nodes := graphNodes(graph)
	known := map[string]struct{}{}
	for _, node := range nodes {
		known[node] = struct{}{}
	}
	index := 0
	stack := []string{}
	onStack := map[string]bool{}
	indices, lowlink := map[string]int{}, map[string]int{}
	components := [][]string{}

	var visit func(string)
	visit = func(node string) {
		indices[node] = index
		lowlink[node] = index
		index++
		stack = append(stack, node)
		onStack[node] = true

		for _, target := range normalizedTargets(graph, node, known) {
			if _, ok := indices[target]; !ok {
				visit(target)
				if lowlink[target] < lowlink[node] {
					lowlink[node] = lowlink[target]
				}
			} else if onStack[target] && indices[target] < lowlink[node] {
				lowlink[node] = indices[target]
			}
		}
		if lowlink[node] == indices[node] {
			component := []string{}
			for len(stack) > 0 {
				member := stack[len(stack)-1]
				stack = stack[:len(stack)-1]
				onStack[member] = false
				component = append(component, member)
				if member == node {
					break
				}
			}
			sort.Strings(component)
			components = append(components, component)
		}
	}
	for _, node := range nodes {
		if _, ok := indices[node]; !ok {
			visit(node)
		}
	}
	sort.Slice(components, func(i, j int) bool {
		if len(components[i]) == 0 || len(components[j]) == 0 {
			return len(components[i]) < len(components[j])
		}
		if components[i][0] == components[j][0] {
			return len(components[i]) < len(components[j])
		}
		return components[i][0] < components[j][0]
	})
	return components
}

func BrandesBetweenness(graph Graph) map[string]float64 {
	nodes := graphNodes(graph)
	known := map[string]struct{}{}
	for _, node := range nodes {
		known[node] = struct{}{}
	}
	score := map[string]float64{}
	for _, node := range nodes {
		score[node] = 0
	}
	for _, source := range nodes {
		stack := []string{}
		predecessors := map[string][]string{}
		sigma := map[string]float64{}
		distance := map[string]int{}
		for _, node := range nodes {
			predecessors[node] = []string{}
			sigma[node] = 0
			distance[node] = -1
		}
		sigma[source], distance[source] = 1, 0
		queue := []string{source}
		for len(queue) > 0 {
			vertex := queue[0]
			queue = queue[1:]
			stack = append(stack, vertex)
			for _, target := range normalizedTargets(graph, vertex, known) {
				if distance[target] < 0 {
					queue = append(queue, target)
					distance[target] = distance[vertex] + 1
				}
				if distance[target] == distance[vertex]+1 {
					sigma[target] += sigma[vertex]
					predecessors[target] = append(predecessors[target], vertex)
				}
			}
		}
		dependency := map[string]float64{}
		for _, node := range nodes {
			dependency[node] = 0
		}
		for len(stack) > 0 {
			target := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			if sigma[target] > 0 {
				coefficient := (1 + dependency[target]) / sigma[target]
				for _, predecessor := range predecessors[target] {
					dependency[predecessor] += sigma[predecessor] * coefficient
				}
			}
			if target != source {
				score[target] += dependency[target]
			}
		}
	}
	maximum := 0.0
	for _, value := range score {
		if value > maximum {
			maximum = value
		}
	}
	if maximum <= 0 {
		maximum = 1
	}
	for node := range score {
		score[node] /= maximum
	}
	return score
}

type degreeItem struct {
	degree int
	node   string
	index  int
}
type degreeHeap []*degreeItem
func (h degreeHeap) Len() int { return len(h) }
func (h degreeHeap) Less(i, j int) bool {
	if h[i].degree == h[j].degree { return h[i].node < h[j].node }
	return h[i].degree < h[j].degree
}
func (h degreeHeap) Swap(i, j int) { h[i], h[j] = h[j], h[i]; h[i].index=i; h[j].index=j }
func (h *degreeHeap) Push(x any) { item:=x.(*degreeItem); item.index=len(*h); *h=append(*h,item) }
func (h *degreeHeap) Pop() any { old:=*h; n:=len(old); item:=old[n-1]; *h=old[:n-1]; return item }

func KCoreNumbers(graph Graph) map[string]float64 {
	nodes := graphNodes(graph)
	adjacency := map[string]map[string]struct{}{}
	for _, node := range nodes { adjacency[node]=map[string]struct{}{} }
	for source, targets := range graph {
		for _, target := range targets {
			if target==source { continue }
			if _,ok:=adjacency[target]; !ok { continue }
			adjacency[source][target]=struct{}{}
			adjacency[target][source]=struct{}{}
		}
	}
	degree:=map[string]int{}
	h:=degreeHeap{}
	for _,node:=range nodes {
		degree[node]=len(adjacency[node])
		heap.Push(&h,&degreeItem{degree:degree[node],node:node})
	}
	heap.Init(&h)
	removed:=map[string]bool{}
	core:=map[string]int{}
	degeneracy:=0
	for h.Len()>0 {
		item:=heap.Pop(&h).(*degreeItem)
		if removed[item.node] || degree[item.node]!=item.degree { continue }
		removed[item.node]=true
		if item.degree>degeneracy { degeneracy=item.degree }
		core[item.node]=degeneracy
		for neighbor:=range adjacency[item.node] {
			if removed[neighbor] { continue }
			degree[neighbor]--
			heap.Push(&h,&degreeItem{degree:degree[neighbor],node:neighbor})
		}
	}
	maximum:=1
	for _,value:=range core { if value>maximum { maximum=value } }
	out:=map[string]float64{}
	for _,node:=range nodes { out[node]=float64(core[node])/float64(maximum) }
	return out
}

func GraphGallery(graph Graph, seeds map[string]float64) map[string]Gallery {
	pr:=PageRank(graph,0.85,48,seeds)
	hubs,auth:=HITS(graph,32)
	katz:=Katz(graph,0,1,40)
	between:=BrandesBetweenness(graph)
	core:=KCoreNumbers(graph)
	components:=TarjanSCC(graph)
	cyclic:=map[string]bool{}
	for _,component:=range components {
		if len(component)>1 { for _,node:=range component { cyclic[node]=true } }
	}
	normalize:=func(values map[string]float64,node string) float64 {
		maximum:=0.0
		for _,value:=range values { if value>maximum { maximum=value } }
		if maximum<=0 { return 0 }
		return values[node]/maximum
	}
	out:=map[string]Gallery{}
	for _,node:=range graphNodes(graph) {
		cycle:=0.0
		if cyclic[node] { cycle=1 }
		out[node]=NewGallery("graph",[]Vote{
			{Exhibit:"pagerank",Score:normalize(pr,node)},
			{Exhibit:"hits-hub",Score:normalize(hubs,node)},
			{Exhibit:"hits-authority",Score:normalize(auth,node)},
			{Exhibit:"katz",Score:katz[node]},
			{Exhibit:"brandes",Score:between[node]},
			{Exhibit:"k-core",Score:core[node]},
			{Exhibit:"tarjan-cycle",Score:cycle},
		})
	}
	return out
}
