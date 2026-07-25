import { describe, expect, it } from "vitest";
import { chipLabel, splitTokens } from "./SearchBar";

describe("splitTokens", () => {
  it("splits on spaces but keeps quoted values together", () => {
    expect(splitTokens('coffee merchant:"blue bottle" >50')).toEqual([
      "coffee",
      'merchant:"blue bottle"',
      ">50",
    ]);
  });

  it("returns an empty list for blank input", () => {
    expect(splitTokens("")).toEqual([]);
    expect(splitTokens("   ")).toEqual([]);
  });
});

describe("chipLabel", () => {
  it("renders field tokens as readable labels", () => {
    expect(chipLabel("merchant:Costco")).toBe("Merchant: Costco");
    expect(chipLabel('merchant:"Blue Bottle"')).toBe("Merchant: Blue Bottle");
    expect(chipLabel("cat:FOOD")).toBe("Category: FOOD");
  });

  it("renders amount bounds as money", () => {
    expect(chipLabel(">50")).toBe("Over $50");
    expect(chipLabel("<100")).toBe("Under $100");
  });

  it("renders status flags bare and passes free text through", () => {
    expect(chipLabel("is:unreviewed")).toBe("unreviewed");
    expect(chipLabel("coffee")).toBe("coffee");
  });
});
