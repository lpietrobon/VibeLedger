import { describe, expect, it } from "vitest";
import {
  buildCategoryTree,
  createSuggestion,
  filterCategories,
  leafLabel,
  normalizeCategory,
  parentOf,
  recentCategories,
  scoreCategory,
} from "./CategoryPicker";
import type { CategoryEntry } from "@/lib/api/types";

const entry = (value: string, count = 0): CategoryEntry => ({
  value,
  count,
  source: count > 0 ? "ledger" : "default",
});

describe("normalizeCategory", () => {
  it("trims, collapses slashes, and uppercases", () => {
    expect(normalizeCategory("FOOD//DINING")).toBe("FOOD/DINING");
    expect(normalizeCategory("  food/dining  ")).toBe("FOOD/DINING");
    expect(normalizeCategory("food and drink")).toBe("FOOD_AND_DRINK");
    expect(normalizeCategory("")).toBe("");
  });
});

describe("parentOf / leafLabel", () => {
  it("handles 1, 2 and 3 levels", () => {
    expect(parentOf("BANK_FEES")).toBe("");
    expect(parentOf("FOOD/DINING")).toBe("FOOD");
    expect(parentOf("FOOD/DINING/SUSHI")).toBe("FOOD/DINING");
    expect(leafLabel("BANK_FEES")).toBe("BANK_FEES");
    expect(leafLabel("FOOD/DINING/SUSHI")).toBe("SUSHI");
  });
});

describe("buildCategoryTree", () => {
  it("synthesizes parents that only exist via a child path", () => {
    const roots = buildCategoryTree([entry("TRANSPORT/FUEL", 3)]);
    expect(roots).toHaveLength(1);
    expect(roots[0].value).toBe("TRANSPORT");
    expect(roots[0].exists).toBe(false); // never used on its own
    expect(roots[0].children.map((c) => c.value)).toEqual(["TRANSPORT/FUEL"]);
  });

  it("marks a parent that is itself used as existing, and rolls counts up", () => {
    const roots = buildCategoryTree([entry("FOOD", 2), entry("FOOD/DINING", 5)]);
    expect(roots[0].exists).toBe(true);
    expect(roots[0].count).toBe(2);
    expect(roots[0].totalCount).toBe(7); // own + children
  });

  it("keeps a 1-level category as a childless root", () => {
    const roots = buildCategoryTree([entry("TRANSFER_IN", 4)]);
    expect(roots[0].children).toHaveLength(0);
    expect(roots[0].totalCount).toBe(4);
  });

  it("nests three levels", () => {
    const roots = buildCategoryTree([entry("FOOD/DINING/SUSHI", 1)]);
    expect(roots[0].value).toBe("FOOD");
    expect(roots[0].children[0].value).toBe("FOOD/DINING");
    expect(roots[0].children[0].children[0].value).toBe("FOOD/DINING/SUSHI");
    expect(roots[0].totalCount).toBe(1);
  });

  it("merges case variants into one node with summed counts", () => {
    const roots = buildCategoryTree([entry("uncategorized", 3), entry("UNCATEGORIZED", 2)]);
    expect(roots).toHaveLength(1);
    expect(roots[0].value).toBe("UNCATEGORIZED");
    expect(roots[0].count).toBe(5);
  });

  it("orders roots by subtree total, descending", () => {
    const roots = buildCategoryTree([entry("FOOD/DINING", 1), entry("HOUSING", 9)]);
    expect(roots.map((r) => r.value)).toEqual(["HOUSING", "FOOD"]);
  });
});

describe("scoreCategory / filterCategories", () => {
  const entries = [entry("FOOD", 4), entry("FOOD/DINING", 9), entry("FOOD/OTHER", 2), entry("HOUSING", 1)];

  it("ranks an exact match above its children", () => {
    expect(scoreCategory("FOOD", "food")).toBeGreaterThan(scoreCategory("FOOD/OTHER", "food"));
  });

  it("matches a child by its leaf", () => {
    expect(filterCategories(entries, "din")[0].value).toBe("FOOD/DINING");
  });

  it("treats spaces and slashes interchangeably", () => {
    expect(filterCategories(entries, "food din")[0].value).toBe("FOOD/DINING");
    expect(filterCategories(entries, "food/din")[0].value).toBe("FOOD/DINING");
  });

  it("is case-insensitive and returns everything for an empty query", () => {
    expect(filterCategories(entries, "HOUSING")[0].value).toBe("HOUSING");
    expect(filterCategories(entries, "  ")).toHaveLength(entries.length);
  });

  it("excludes non-matches", () => {
    expect(filterCategories(entries, "zzz")).toEqual([]);
  });
});

describe("recentCategories", () => {
  it("returns only used categories, most used first, capped", () => {
    const entries = [entry("A", 1), entry("B", 9), entry("C", 0), entry("D", 5)];
    expect(recentCategories(entries, 2).map((e) => e.value)).toEqual(["B", "D"]);
    expect(recentCategories(entries).some((e) => e.value === "C")).toBe(false);
  });
});

describe("createSuggestion", () => {
  const entries = [entry("FOOD/DINING", 1)];

  it("creates under the current parent when drilled in", () => {
    expect(createSuggestion("sushi", "FOOD", entries)).toBe("FOOD/SUSHI");
  });

  it("creates a bare top-level value at the root", () => {
    expect(createSuggestion("pets", "", entries)).toBe("PETS");
  });

  it("treats input containing a slash as absolute even when drilled in", () => {
    expect(createSuggestion("transport/fuel", "FOOD", entries)).toBe("TRANSPORT/FUEL");
  });

  it("returns null when empty or already present", () => {
    expect(createSuggestion("", "FOOD", entries)).toBeNull();
    expect(createSuggestion("  ", "", entries)).toBeNull();
    expect(createSuggestion("food/dining", "", entries)).toBeNull();
    expect(createSuggestion("dining", "FOOD", entries)).toBeNull(); // resolves to an existing value
  });
});
