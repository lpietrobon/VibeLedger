import { afterEach, describe, expect, it, vi } from "vitest";
import { getTransactions } from "./client";

function mockFetch() {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => ({ total: 4, items: [] }),
  })) as unknown as typeof fetch;
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock as unknown as ReturnType<typeof vi.fn>;
}

afterEach(() => vi.unstubAllGlobals());

describe("PI-13 category drilldown request contract", () => {
  it("constructs the inclusive server-bounded exact-category spend request", async () => {
    const fetchMock = mockFetch();
    await getTransactions({
      category: "FOOD/OTHER",
      query: "is:spend",
      startDate: "2032-04-01",
      endDate: "2032-04-30",
      limit: 2,
      offset: 2,
    });

    const [input] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    const url = new URL(String(input));
    expect(url.pathname).toBe("/vibeledger/api/transactions");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      start_date: "2032-04-01",
      end_date: "2032-04-30",
      category: "FOOD/OTHER",
      q: "is:spend",
      limit: "2",
      offset: "2",
    });
  });
});
