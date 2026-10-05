import type {
  Candidate,
  DashboardProjection,
  GalleryEvidence,
  MuseumEvidence,
} from "./types.js";

const galleryEntries = (
  museum: MuseumEvidence,
): [string, GalleryEvidence][] => [
  ["robust", museum.robust],
  ["change", museum.change],
  ["information", museum.information],
  ["graph", museum.graph],
  ["exploration", museum.exploration],
  ["sketches", museum.sketches],
];

export function dominantGallery(museum: MuseumEvidence): string {
  return galleryEntries(museum)
    .sort(
      (left, right) =>
        right[1].consensus - left[1].consensus ||
        left[0].localeCompare(right[0]),
    )[0]?.[0] ?? "unknown";
}

export function projectCandidate(candidate: Candidate): DashboardProjection {
  const surprise =
    candidate.museum.information.votes.find(
      (vote) => vote.exhibit.includes("surprise"),
    )?.score ?? candidate.change_probability;

  return {
    repository: candidate.name,
    ecosystem: candidate.ecosystem,
    utility: candidate.utility,
    risk: candidate.tail_risk,
    novelty: candidate.structural_novelty,
    surprise,
    consensus: candidate.museum.consensus,
    disagreement: candidate.museum.disagreement,
    dominantGallery: dominantGallery(candidate.museum),
    reasons: [...candidate.reasons],
  };
}

export function projectCandidates(
  candidates: readonly Candidate[],
): DashboardProjection[] {
  return candidates
    .map(projectCandidate)
    .sort(
      (a, b) =>
        b.utility - a.utility ||
        b.consensus - a.consensus ||
        a.repository.localeCompare(b.repository),
    );
}

export function galleryRadar(
  museum: MuseumEvidence,
): { axis: string; value: number; disagreement: number }[] =>
  galleryEntries(museum).map(([axis, gallery]) => ({
    axis,
    value: gallery.consensus,
    disagreement: gallery.disagreement,
  }));

export function exhibitHeatmap(
  candidates: readonly Candidate[],
): {
  exhibits: string[];
  repositories: string[];
  values: number[][];
} {
  const exhibits = [
    ...new Set(
      candidates.flatMap((candidate) =>
        galleryEntries(candidate.museum).flatMap(([, gallery]) =>
          gallery.votes.map((vote) => vote.exhibit),
        ),
      ),
    ),
  ].sort();

  const repositories = candidates.map((candidate) => candidate.name);
  const values = candidates.map((candidate) => {
    const scores = new Map(
      galleryEntries(candidate.museum).flatMap(([, gallery]) =>
        gallery.votes.map((vote) => [vote.exhibit, vote.score] as const),
      ),
    );
    return exhibits.map((exhibit) => scores.get(exhibit) ?? 0);
  });
  return { exhibits, repositories, values };
}

export function disagreementQueue(
  candidates: readonly Candidate[],
  threshold = 0.4,
): DashboardProjection[] =>
  projectCandidates(candidates)
    .filter((candidate) => candidate.disagreement >= threshold)
    .sort(
      (a, b) =>
        b.disagreement - a.disagreement ||
        b.utility - a.utility ||
        a.repository.localeCompare(b.repository),
    );

export function ecosystemMatrix(
  candidates: readonly Candidate[],
): {
  ecosystems: string[];
  metrics: string[];
  values: number[][];
} {
  const ecosystems = [...new Set(candidates.map((candidate) => candidate.ecosystem))].sort();
  const metrics = ["utility", "risk", "novelty", "consensus", "disagreement"];
  const values = ecosystems.map((ecosystem) => {
    const rows = candidates.filter((candidate) => candidate.ecosystem === ecosystem);
    if (rows.length === 0) return metrics.map(() => 0);
    const average = (selector: (candidate: Candidate) => number): number =>
      rows.reduce((sum, candidate) => sum + selector(candidate), 0) / rows.length;
    return [
      average((candidate) => candidate.utility),
      average((candidate) => candidate.tail_risk),
      average((candidate) => candidate.structural_novelty),
      average((candidate) => candidate.museum.consensus),
      average((candidate) => candidate.museum.disagreement),
    ];
  });
  return { ecosystems, metrics, values };
}

export function explainCandidate(candidate: Candidate): string[] {
  const output: string[] = [];
  output.push(
    `${candidate.name}: utility ${candidate.utility.toFixed(3)}, risk ${candidate.tail_risk.toFixed(3)}`,
  );
  output.push(
    `Museum consensus ${candidate.museum.consensus.toFixed(3)} with disagreement ${candidate.museum.disagreement.toFixed(3)}`,
  );

  for (const [name, gallery] of galleryEntries(candidate.museum).sort(
    (a, b) => b[1].consensus - a[1].consensus,
  )) {
    const leaders = [...gallery.votes]
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map((vote) => `${vote.exhibit}=${vote.score.toFixed(2)}`)
      .join(", ");
    output.push(
      `${name}: consensus ${gallery.consensus.toFixed(3)}; ${leaders || "no votes"}`,
    );
  }

  if (candidate.reasons.length > 0) {
    output.push(`Reasons: ${candidate.reasons.join(", ")}`);
  }
  return output;
}
