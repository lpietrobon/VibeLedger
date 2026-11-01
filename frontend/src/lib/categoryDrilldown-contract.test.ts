import { describe, expect, it } from "vitest";
import { categoryDrilldownHref } from "./categoryDrilldown";

describe("INSP-01 spending-category drilldown contract", () => {
  it("keeps the exact posted-spending server scope and optional source context", () => {
    const href = categoryDrilldownHref({
      category: "FOOD/OTHER",
      startDate: "2032-04-01",
      endDate: "2032-04-30",
      source: "spending",
      comparison: "current",
    });
    const url = new URL(href, window.location.origin);
    expect(Object.fromEntries(url.searchParams)).toEqual({
      category: "FOOD/OTHER", query: "is:spend", startDate: "2032-04-01",
      endDate: "2032-04-30", sort: "date", order: "desc",
      source: "spending", comparison: "current",
    });
  });
});
