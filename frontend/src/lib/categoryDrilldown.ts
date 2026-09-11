export type CategoryDrilldown = {
  category: string;
  startDate: string;
  endDate: string;
};

const basePath = import.meta.env.BASE_URL.replace(/\/+$/, "");

/**
 * Build the canonical Activity destination for an inspectable spending
 * aggregate. Keeping this here prevents each reporting surface from inventing
 * its own category/query/date semantics.
 */
export function categoryDrilldownHref({ category, startDate, endDate }: CategoryDrilldown) {
  const params = new URLSearchParams({
    category,
    query: "is:spend",
    startDate,
    endDate,
    sort: "date",
    order: "desc",
  });
  return `${basePath}/transactions?${params.toString()}`;
}
