export interface RadarEvent {
  source: string;
  repository: string;
  observed_at: string;
  event_type: string;
  semantic_impact: number;
  fields?: string[];
}

export interface RepositorySummary {
  repository: string;
  events: number;
  maxImpact: number;
  latestObservedAt: string;
}

export function summarize(events: readonly RadarEvent[]): RepositorySummary[] {
  const map = new Map<string, RepositorySummary>();
  for (const event of events) {
    const current = map.get(event.repository);
    if (!current) {
      map.set(event.repository, {
        repository: event.repository,
        events: 1,
        maxImpact: event.semantic_impact,
        latestObservedAt: event.observed_at,
      });
      continue;
    }
    current.events += 1;
    current.maxImpact = Math.max(current.maxImpact, event.semantic_impact);
    if (event.observed_at > current.latestObservedAt) {
      current.latestObservedAt = event.observed_at;
    }
  }
  return [...map.values()].sort(
    (a, b) => b.maxImpact - a.maxImpact || b.events - a.events || a.repository.localeCompare(b.repository),
  );
}
