export type CategoryDrilldown = {
  category: string;
  startDate: string;
  endDate: string;
  /** Human-readable origin retained by Activity, never interpreted by the API. */
  source?: "overview" | "spending" | "sankey" | "movers";
  comparison?: "current" | "previous";
};

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

/**
 * Build the canonical Activity destination for an inspectable spending
 * aggregate. Keeping this here prevents each reporting surface from inventing
 * its own category/query/date semantics.
 */
export function categoryDrilldownHref({ category, startDate, endDate, source, comparison }: CategoryDrilldown) {
  const params = new URLSearchParams({
    category,
    query: "is:spend",
    startDate,
    endDate,
    sort: "date",
    order: "desc",
  });
  if (source) params.set("source", source);
  if (comparison) params.set("comparison", comparison);
  return `${basePath}/transactions?${params.toString()}`;
}
