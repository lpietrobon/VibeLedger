import { describe, expect, it } from "vitest";
import { comparisonBounds, initialDateSelection, presetBounds, rangeQuery, validateRange } from "./dateRange";

describe("date-only range contract (TIME-02)", () => {
  it("computes inclusive rolling and calendar presets independently of UTC offsets", () => {
    expect(presetBounds("last-30", "2026-10-25")).toEqual({ startDate: "2026-09-26", endDate: "2026-10-25" });
    expect(presetBounds("last-365", "2026-10-25")).toEqual({ startDate: "2025-10-26", endDate: "2026-10-25" });
    expect(presetBounds("current-month", "2026-10-25")).toEqual({ startDate: "2026-10-01", endDate: "2026-10-25" });
    expect(presetBounds("current-year", "2026-10-25")).toEqual({ startDate: "2026-01-01", endDate: "2026-10-25" });
  });
  it("maps comparison to corresponding dates with month-end and leap clipping", () => {
    expect(comparisonBounds({ startDate: "2026-10-05", endDate: "2026-10-15" }, "previous-month"))
      .toEqual({ startDate: "2026-09-05", endDate: "2026-09-15" });
    expect(comparisonBounds({ startDate: "2026-03-29", endDate: "2026-03-31" }, "previous-month"))
      .toEqual({ startDate: "2026-02-28", endDate: "2026-02-28" });
    expect(comparisonBounds({ startDate: "2024-02-29", endDate: "2024-03-04" }, "previous-year"))
      .toEqual({ startDate: "2023-02-28", endDate: "2023-03-04" });
    expect(comparisonBounds({ startDate: "2026-01-02", endDate: "2026-01-04" }, "previous-period"))
      .toEqual({ startDate: "2025-12-30", endDate: "2026-01-01" });
  });
  it("does not force a comparison or permit invalid day ranges", () => {
    expect(rangeQuery(initialDateSelection("last-30", "2026-10-25"))).toEqual({
      startDate: "2026-09-26", endDate: "2026-10-25",
      compareStartDate: undefined, compareEndDate: undefined,
    });
    expect(validateRange({ startDate: "2026-02-30", endDate: "2026-03-01" })).toBe(false);
    expect(validateRange({ startDate: "2026-10-15", endDate: "2026-10-05" })).toBe(false);
    expect(validateRange({ startDate: "", endDate: "" }, true)).toBe(true);
  });
});
