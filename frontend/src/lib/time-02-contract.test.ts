import { afterEach, expect, it, vi } from "vitest";
import { comparisonBounds, initialDateSelection, localToday, presetBounds, rangeQuery, validateRange } from "./dateRange";
import { getCategoryMovers } from "./api/client";
afterEach(() => vi.unstubAllGlobals());
it.each([
 ["current-month", "2024-02-29", "2024-02-01", "2024-02-29"],
 ["current-year", "2024-02-29", "2024-01-01", "2024-02-29"],
 ["last-30", "2026-01-15", "2025-12-17", "2026-01-15"],
 ["last-365", "2024-02-29", "2023-03-02", "2024-02-29"],
 ["last-30", "2026-03-09", "2026-02-08", "2026-03-09"],
] as const)("literal inclusive %s at %s", (preset, today, startDate, endDate) => {
 expect(presetBounds(preset, today)).toEqual({ startDate, endDate });
});
it("uses local date at UTC midnight and across DST under TZ=America/Los_Angeles", () => {
 expect(localToday(new Date("2026-03-09T00:30:00Z"))).toBe("2026-03-08");
 expect(localToday(new Date("2026-03-08T09:30:00Z"))).toBe("2026-03-08");
 expect(localToday(new Date("2026-03-08T10:30:00Z"))).toBe("2026-03-08");
});
it.each([
 ["previous-month", "2026-09-05", "2026-09-15"],
 ["previous-year", "2025-10-05", "2025-10-15"],
 ["previous-period", "2026-09-24", "2026-10-04"],
] as const)("serializes independently selected %s", (comparison, compareStartDate, compareEndDate) => {
 expect(rangeQuery({ preset: "custom", startDate: "2026-10-05", endDate: "2026-10-15", comparison }))
 .toEqual({ startDate: "2026-10-05", endDate: "2026-10-15", compareStartDate, compareEndDate });
});
it.each(["current-month", "current-year", "last-30", "last-365", "custom"] as const)("does not infer comparison from %s", (preset) => {
 const selection = initialDateSelection(preset, "2026-10-25");
 expect(rangeQuery(selection)?.compareStartDate).toBeUndefined();
 expect(rangeQuery(selection)?.compareEndDate).toBeUndefined();
});
it("clips original endpoints without equalizing duration", () => {
 expect(comparisonBounds({ startDate: "2026-03-29", endDate: "2026-03-31" }, "previous-month")).toEqual({ startDate: "2026-02-28", endDate: "2026-02-28" });
 expect(comparisonBounds({ startDate: "2024-02-29", endDate: "2024-03-04" }, "previous-year")).toEqual({ startDate: "2023-02-28", endDate: "2023-03-04" });
 expect(comparisonBounds({ startDate: "2026-01-31", endDate: "2026-01-31" }, "previous-month")).toEqual({ startDate: "2025-12-31", endDate: "2025-12-31" });
});
it.each([["2026-02-29", "2026-03-01"], ["2026-10-15", "2026-10-05"], ["", "2026-10-05"]])("blocks invalid %s–%s", (startDate, endDate) => {
 expect(rangeQuery({ preset: "custom", comparison: "none", startDate, endDate })).toBeNull();
});
it("preserves all-time absence and future dates", () => {
 expect(rangeQuery(initialDateSelection("all", "2026-10-25"))).toEqual({ startDate: undefined, endDate: undefined, compareStartDate: undefined, compareEndDate: undefined });
 expect(validateRange({ startDate: "2032-01-01", endDate: "2032-01-02" })).toBe(true);
});
it.each(["none", "previous-month"] as const)("maps %s to HTTP bounds with empty history", async (comparison) => {
 const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ month: "2026-10", previous_month: null, items: [] }) });
 vi.stubGlobal("fetch", fetchMock);
 const result = await getCategoryMovers(rangeQuery({ preset: "custom", comparison, startDate: "2026-10-05", endDate: "2026-10-15" })!);
 const url = new URL(String(fetchMock.mock.calls[0][0]));
 expect(url.searchParams.get("start_date")).toBe("2026-10-05");
 expect(url.searchParams.get("end_date")).toBe("2026-10-15");
 expect(url.searchParams.get("compare_start_date")).toBe(comparison === "none" ? null : "2026-09-05");
 expect(url.searchParams.get("compare_end_date")).toBe(comparison === "none" ? null : "2026-09-15");
 expect(result.items).toEqual([]);
});
