import type {
  Exhibit,
  FamilySummary,
  MuseumCatalog,
  TimelineEntry,
} from "./types.js";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asString = (value: unknown, field: string): string => {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new TypeError(`${field} must be a non-empty string`);
  }
  return value.trim();
};

const asNumber = (value: unknown, field: string): number => {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${field} must be a finite number`);
  }
  return value;
};

const parseExhibit = (value: unknown, index: number): Exhibit => {
  if (!isRecord(value)) {
    throw new TypeError(`exhibits[${index}] must be an object`);
  }
  const introduced = Math.trunc(asNumber(value.introduced, "introduced"));
  if (introduced < 1600 || introduced > 2200) {
    throw new RangeError(`exhibits[${index}].introduced is implausible`);
  }
  return {
    slug: asString(value.slug, "slug"),
    name: asString(value.name, "name"),
    family: asString(value.family, "family"),
    introduced,
    complexity: asString(value.complexity, "complexity"),
    role: asString(value.role, "role"),
    production: Boolean(value.production),
    notes: typeof value.notes === "string" ? value.notes : "",
  };
};

export function parseCatalog(value: unknown): MuseumCatalog {
  if (!isRecord(value)) {
    throw new TypeError("catalog must be an object");
  }
  if (!Array.isArray(value.exhibits)) {
    throw new TypeError("catalog.exhibits must be an array");
  }
  const exhibits = value.exhibits.map(parseExhibit);
  const slugs = new Set<string>();
  for (const exhibit of exhibits) {
    if (slugs.has(exhibit.slug)) {
      throw new Error(`duplicate exhibit slug: ${exhibit.slug}`);
    }
    slugs.add(exhibit.slug);
  }

  const families = [...new Set(exhibits.map((item) => item.family))].sort();
  const count =
    typeof value.count === "number" ? Math.trunc(value.count) : exhibits.length;
  if (count !== exhibits.length) {
    throw new Error(
      `catalog count mismatch: declared ${count}, actual ${exhibits.length}`,
    );
  }

  return {
    version:
      typeof value.version === "number" ? Math.trunc(value.version) : 1,
    count,
    families,
    exhibits: [...exhibits].sort(
      (a, b) => a.introduced - b.introduced || a.slug.localeCompare(b.slug),
    ),
  };
}

export function timeline(catalog: MuseumCatalog): TimelineEntry[] {
  const byYear = new Map<number, Exhibit[]>();
  for (const exhibit of catalog.exhibits) {
    const list = byYear.get(exhibit.introduced) ?? [];
    list.push(exhibit);
    byYear.set(exhibit.introduced, list);
  }
  return [...byYear.entries()]
    .sort(([a], [b]) => a - b)
    .map(([year, exhibits]) => ({
      year,
      exhibits: [...exhibits].sort((a, b) => a.name.localeCompare(b.name)),
      production: exhibits.filter((item) => item.production).length,
      reference: exhibits.filter((item) => !item.production).length,
    }));
}

const median = (values: readonly number[]): number => {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[middle - 1]! + sorted[middle]!) / 2
    : sorted[middle]!;
};

export function summarizeFamilies(catalog: MuseumCatalog): FamilySummary[] {
  const grouped = new Map<string, Exhibit[]>();
  for (const exhibit of catalog.exhibits) {
    const list = grouped.get(exhibit.family) ?? [];
    list.push(exhibit);
    grouped.set(exhibit.family, list);
  }

  return [...grouped.entries()]
    .map(([family, exhibits]) => {
      const years = exhibits.map((item) => item.introduced);
      return {
        family,
        count: exhibits.length,
        production: exhibits.filter((item) => item.production).length,
        reference: exhibits.filter((item) => !item.production).length,
        earliest: Math.min(...years),
        latest: Math.max(...years),
        medianYear: median(years),
        complexities: [...new Set(exhibits.map((item) => item.complexity))].sort(),
      };
    })
    .sort(
      (a, b) =>
        b.count - a.count ||
        a.earliest - b.earliest ||
        a.family.localeCompare(b.family),
    );
}

export function searchExhibits(
  catalog: MuseumCatalog,
  query: string,
): Exhibit[] {
  const terms = query
    .toLocaleLowerCase()
    .split(/\s+/u)
    .map((term) => term.trim())
    .filter(Boolean);
  if (terms.length === 0) return [...catalog.exhibits];

  return catalog.exhibits
    .map((exhibit) => {
      const haystack = [
        exhibit.slug,
        exhibit.name,
        exhibit.family,
        exhibit.role,
        exhibit.complexity,
        exhibit.notes,
        String(exhibit.introduced),
      ]
        .join(" ")
        .toLocaleLowerCase();
      const matched = terms.filter((term) => haystack.includes(term)).length;
      const phraseBoost = haystack.includes(query.toLocaleLowerCase()) ? 2 : 0;
      return { exhibit, score: matched + phraseBoost };
    })
    .filter((item) => item.score > 0)
    .sort(
      (a, b) =>
        b.score - a.score ||
        a.exhibit.introduced - b.exhibit.introduced ||
        a.exhibit.name.localeCompare(b.exhibit.name),
    )
    .map((item) => item.exhibit);
}

export function productionCoverage(catalog: MuseumCatalog): {
  total: number;
  production: number;
  reference: number;
  ratio: number;
  uncoveredFamilies: string[];
} {
  const production = catalog.exhibits.filter((item) => item.production);
  const productionFamilies = new Set(production.map((item) => item.family));
  return {
    total: catalog.count,
    production: production.length,
    reference: catalog.count - production.length,
    ratio: catalog.count === 0 ? 0 : production.length / catalog.count,
    uncoveredFamilies: catalog.families.filter(
      (family) => !productionFamilies.has(family),
    ),
  };
}
