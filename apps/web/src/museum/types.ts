export type AlgorithmFamily =
  | "robust-statistics"
  | "change-detection"
  | "bayesian-change-detection"
  | "information-theory"
  | "graph-centrality"
  | "graph-structure"
  | "online-learning"
  | "streaming-sketch"
  | "submodular-optimization"
  | "combinatorial-optimization"
  | "multiobjective-optimization"
  | string;

export interface Exhibit {
  slug: string;
  name: string;
  family: AlgorithmFamily;
  introduced: number;
  complexity: string;
  role: string;
  production: boolean;
  notes: string;
}

export interface MuseumCatalog {
  version: number;
  count: number;
  families: string[];
  exhibits: Exhibit[];
}

export interface Vote {
  exhibit: string;
  score: number;
}

export interface GalleryEvidence {
  family: string;
  consensus: number;
  disagreement: number;
  votes: Vote[];
}

export interface MuseumEvidence {
  robust: GalleryEvidence;
  change: GalleryEvidence;
  information: GalleryEvidence;
  graph: GalleryEvidence;
  exploration: GalleryEvidence;
  sketches: GalleryEvidence;
  consensus: number;
  disagreement: number;
}

export interface Candidate {
  name: string;
  ecosystem: string;
  cost: number;
  change_probability: number;
  uncertainty: number;
  local_signal: number;
  graph_influence: number;
  structural_novelty: number;
  tail_risk: number;
  reliability: number;
  exploration: number;
  risk_adjusted_utility: number;
  utility: number;
  museum: MuseumEvidence;
  reasons: string[];
  tags: string[];
}

export interface RepositorySignal {
  name: string;
  ecosystem: string;
  cost: number;
  freshness_hours: number;
  commit_velocity?: number;
  release_velocity?: number;
  issue_velocity?: number;
  contributor_velocity?: number;
  maintainer_activity?: number;
  security_signal?: number;
  breakage_risk?: number;
  dependency_importance?: number;
  novelty?: number;
  downstream_relevance?: number;
  recent_change_hits?: number;
  recent_change_misses?: number;
  observation_count?: number;
  failure_streak?: number;
  source_reliability?: number;
  change_history?: number[];
  impact_history?: number[];
  dependencies?: string[];
  tags?: string[];
}

export interface TimelineEntry {
  year: number;
  exhibits: Exhibit[];
  production: number;
  reference: number;
}

export interface FamilySummary {
  family: string;
  count: number;
  production: number;
  reference: number;
  earliest: number;
  latest: number;
  medianYear: number;
  complexities: string[];
}

export interface ParetoPoint {
  name: string;
  utility: number;
  novelty: number;
  risk: number;
  cost?: number;
  ecosystem?: string;
}

export interface PortfolioAudit {
  production: string[];
  exactKnapsack: string[];
  pareto: string[];
  celf: string[];
  utilityRatio: number;
}

export interface GraphNode {
  id: string;
  label?: string;
  ecosystem?: string;
  weight?: number;
  metadata?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight?: number;
}

export interface GraphModel {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CentralityBundle {
  pageRank: Map<string, number>;
  hubs: Map<string, number>;
  authorities: Map<string, number>;
  katz: Map<string, number>;
  betweenness: Map<string, number>;
  core: Map<string, number>;
  components: string[][];
}

export interface DistributionShift {
  jsd: number;
  wasserstein: number;
  mmd: number;
  consensus: number;
  disagreement: number;
}

export interface DashboardProjection {
  repository: string;
  ecosystem: string;
  utility: number;
  risk: number;
  novelty: number;
  surprise: number;
  consensus: number;
  disagreement: number;
  dominantGallery: string;
  reasons: string[];
}
