import { describe, expect, it } from "vitest";
import { comparisonBounds, comparisonPeriods, initialDateSelection, presetBounds, rangeQuery, trendGranularity, validateRange } from "./dateRange";

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

describe("unified multi-period chart contract", () => {
  it("maps three previous months from the original dates, not recursively clipped prior dates", () => {
    const selection = initialDateSelection("current-month", "2026-03-31");
    expect(comparisonPeriods(selection, 3)).toEqual([
      { startDate: "2026-02-01", endDate: "2026-02-28" },
      { startDate: "2026-01-01", endDate: "2026-01-31" },
      { startDate: "2025-12-01", endDate: "2025-12-31" },
    ]);
    expect(comparisonPeriods(selection, 0)).toEqual([]);
    // Chart count=0 does not suppress the always-on KPI prior comparison.
    expect(rangeQuery(selection)?.compareEndDate).toBe("2026-02-28");
  });
  it("maps previous years with leap-day clipping and contiguous rolling windows", () => {
    const annual = initialDateSelection("current-year", "2024-02-29");
    expect(comparisonPeriods(annual, 2)).toEqual([
      { startDate: "2023-01-01", endDate: "2023-02-28" },
      { startDate: "2022-01-01", endDate: "2022-02-28" },
    ]);
    const rolling = initialDateSelection("last-30", "2026-10-25");
    expect(comparisonPeriods(rolling, 2)).toEqual([
      { startDate: "2026-08-27", endDate: "2026-09-25" },
      { startDate: "2026-07-28", endDate: "2026-08-26" },
    ]);
    const custom = { ...initialDateSelection("custom", "2026-10-25"),
      startDate: "2026-10-06", endDate: "2026-10-18" };
    expect(comparisonPeriods(custom, 1)).toEqual([
      { startDate: "2026-09-23", endDate: "2026-10-05" },
    ]);
  });
  it("uses daily cashflow for short windows and monthly resolution for long ones", () => {
    expect(trendGranularity({startDate:"2026-10-01",endDate:"2026-10-25"})).toBe("daily");
    expect(trendGranularity({startDate:"2026-09-01",endDate:"2026-10-25"})).toBe("monthly");
  });
});
