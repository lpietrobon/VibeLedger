import { describe, expect, it } from "vitest";
import { formatDate } from "./format";

const referenceDate = new Date("2026-09-18T12:00:00Z");

describe("PI-25 current-year-aware date formatting contract", () => {
  it("omits the year only for dates in the supplied reference year", () => {
    expect(formatDate("2026-09-02", { referenceDate })).toBe("2 Sep");
    expect(formatDate("2025-09-02", { referenceDate })).toBe("2 Sep, 2025");
    expect(formatDate("2027-09-02", { referenceDate })).toBe("2 Sep, 2027");
  });

  it("is deterministic at year boundaries and for leap days", () => {
    expect(formatDate("2026-01-01", { referenceDate })).toBe("1 Jan");
    expect(formatDate("2025-12-31", { referenceDate })).toBe("31 Dec, 2025");
    expect(formatDate("2024-02-29", { referenceDate })).toBe("29 Feb, 2024");
  });

  it("treats date-only values as calendar dates independent of host timezone", () => {
    expect(formatDate("2026-09-02", { referenceDate })).toBe("2 Sep");
    expect(formatDate("2026-09-02T23:30:00-07:00", { referenceDate })).toBe("2 Sep");
  });

  it("never renders an invalid user-facing date string", () => {
    expect(formatDate(undefined, { referenceDate })).toBe("—");
    expect(formatDate("", { referenceDate })).toBe("—");
    expect(formatDate("not-a-date", { referenceDate })).toBe("—");
    expect(formatDate("2026-02-29", { referenceDate })).toBe("—");
  });
});
