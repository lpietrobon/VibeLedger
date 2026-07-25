import { describe, expect, it } from "vitest";
import { resolveUserCategory } from "./AnnotationSheet";

/**
 * `null` means "keep inheriting" — the rule/Plaid mapping stays live. Getting
 * this wrong silently pins a manual override that then stops responding to
 * rules, which is invisible in the UI, so it's tested directly.
 */

const tx = (category_source: string, effective_category: string) =>
  ({ category_source, effective_category }) as Parameters<typeof resolveUserCategory>[0];

describe("resolveUserCategory", () => {
  it("keeps inheritance when an auto-categorized value is left unchanged", () => {
    expect(resolveUserCategory(tx("plaid", "FOOD/OTHER"), "FOOD/OTHER")).toBeNull();
    expect(resolveUserCategory(tx("rule", "FOOD/COFFEE"), "FOOD/COFFEE")).toBeNull();
    expect(resolveUserCategory(tx("default", "UNCATEGORIZED"), "UNCATEGORIZED")).toBeNull();
  });

  it("keeps inheritance despite case differences (regression)", () => {
    // effective_category is the lowercase SQL fallback literal, while the picker
    // emits canonical uppercase. A case-sensitive compare pinned a manual
    // override on every save of an uncategorized transaction.
    expect(resolveUserCategory(tx("plaid", "uncategorized"), "UNCATEGORIZED")).toBeNull();
    expect(resolveUserCategory(tx("default", "uncategorized"), "UNCATEGORIZED")).toBeNull();
  });

  it("pins the value when the user actually changes it", () => {
    expect(resolveUserCategory(tx("plaid", "FOOD/OTHER"), "FOOD/DINING")).toBe("FOOD/DINING");
    expect(resolveUserCategory(tx("plaid", "uncategorized"), "FOOD/SUSHI")).toBe("FOOD/SUSHI");
  });

  it("never drops an existing manual override", () => {
    // Already manual: even an unchanged value must stay pinned.
    expect(resolveUserCategory(tx("manual", "FOOD/DINING"), "FOOD/DINING")).toBe("FOOD/DINING");
  });

  it("tolerates a missing effective_category", () => {
    expect(resolveUserCategory(tx("plaid", ""), "FOOD/DINING")).toBe("FOOD/DINING");
    expect(resolveUserCategory(tx("plaid", ""), "")).toBeNull();
  });
});
