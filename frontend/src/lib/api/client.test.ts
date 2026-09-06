import { afterEach, describe, expect, it, vi } from "vitest";
import {
  applySuggestion,
  getCategoryCatalog,
  getAccountsSummary,
  getOverviewSummary,
  getCumulativeSpending,
  getSpendingSummary,
  getTransactions,
} from "./client";

/**
 * These guard the API contract mapping: the backend returns snake_case finished
 * numbers, and the client must map them to the camelCase shapes the screens use
 * without re-deriving anything. A silent field rename on either side breaks here.
 */

function mockFetch(payload: unknown) {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    json: async () => payload,
  })) as unknown as typeof fetch;
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock as unknown as ReturnType<typeof vi.fn>;
}

afterEach(() => vi.unstubAllGlobals());

describe("getOverviewSummary", () => {
  it("maps snake_case overview fields to camelCase", async () => {
    mockFetch({
      as_of_date: "2026-03-10",
      net_worth: 1000,
      assets: 1200,
      liabilities: 200,
      month_spend: 500,
      previous_month_spend: 400,
      month_income: 1200,
      previous_month_income: 1000,
      net_cashflow: 700,
      previous_net_cashflow: 600,
      needs_attention: {
        unreviewed_transactions: 5,
        uncategorized_transactions: 2,
        likely_refunds: 1,
        transfer_pairs_pending: 3,
      },
    });

    const s = await getOverviewSummary();
    expect(s.asOfDate).toBe("2026-03-10");
    expect(s.netWorth).toBe(1000);
    expect(s.monthSpend).toBe(500);
    expect(s.previousMonthSpend).toBe(400);
    expect(s.needsAttention.unreviewedTransactions).toBe(5);
    expect(s.needsAttention.transferPairsPending).toBe(3);
  });
});

describe("getAccountsSummary", () => {
  it("preserves explicit account/history coverage metadata", async () => {
    mockFetch({
      assets: 1000,
      liabilities: 200,
      net_worth: 800,
      groups: {},
      coverage: {
        duplicate_account_coverage: "unverified",
        history_coverage: "unverified",
      },
    });

    const summary = await getAccountsSummary();
    expect(summary.coverage).toEqual({
      duplicate_account_coverage: "unverified",
      history_coverage: "unverified",
    });
  });
});

describe("getSpendingSummary", () => {
  it("maps period + driver fields", async () => {
    mockFetch({
      period_label: "March 2026",
      total: 500,
      previous_total: 400,
      change: 100,
      change_pct: 25,
      projection: 500,
      top_driver: { category: "FOOD/OTHER", amount: 100 },
      category_comparison: [],
    });

    const s = await getSpendingSummary({ granularity: "monthly" });
    expect(s.periodLabel).toBe("March 2026");
    expect(s.previousTotal).toBe(400);
    expect(s.changePct).toBe(25);
    expect(s.topDriver).toEqual({ category: "FOOD/OTHER", amount: 100 });
  });
});

describe("getCumulativeSpending", () => {
  it("renames x to day and preserves nulls", async () => {
    mockFetch([
      { x: 1, current: 100, previous1: 50, previous2: null, previous3: null },
      { x: 2, current: null, previous1: 80, previous2: null, previous3: null },
    ]);

    const rows = await getCumulativeSpending({ granularity: "monthly" });
    expect(rows[0]).toEqual({ day: 1, current: 100, previous1: 50, previous2: null, previous3: null });
    expect(rows[1].current).toBeNull();
  });
});

describe("getCategoryCatalog", () => {
  it("unwraps items from the /categories envelope", async () => {
    const fetchMock = mockFetch({
      items: [
        { value: "FOOD/DINING", count: 12, source: "ledger" },
        { value: "PETS/VET", count: 0, source: "rule" },
      ],
    });
    const items = await getCategoryCatalog();
    expect(items).toHaveLength(2);
    expect(items[0]).toEqual({ value: "FOOD/DINING", count: 12, source: "ledger" });
    const calledUrl = new URL(String((fetchMock.mock.calls[0] as unknown[])[0]));
    expect(calledUrl.pathname).toContain("/categories");
  });
});

describe("applySuggestion", () => {
  it("completes a field token and leaves it open for a value", () => {
    // Accepting "Category" from the empty field menu should not add a trailing
    // space — the user still needs to pick a value.
    expect(applySuggestion("", "", "category:")).toBe("category:");
    expect(applySuggestion("cat", "cat", "category:")).toBe("category:");
  });

  it("replaces the in-progress token, preserving earlier terms", () => {
    expect(applySuggestion("coffee merchant:blu", "merchant:blu", 'merchant:"Blue Bottle"')).toBe(
      'coffee merchant:"Blue Bottle" ',
    );
  });

  it("appends a completed value with a trailing space", () => {
    expect(applySuggestion("is:", "is:", "is:unreviewed")).toBe("is:unreviewed ");
  });
});

describe("getTransactions", () => {
  it("passes the search query as ?q=", async () => {
    const fetchMock = mockFetch({ total: 0, items: [] });
    await getTransactions({ query: "coffee", limit: 30 });
    const calledUrl = new URL(String((fetchMock.mock.calls[0] as unknown[])[0]));
    expect(calledUrl.searchParams.get("q")).toBe("coffee");
    expect(calledUrl.searchParams.get("limit")).toBe("30");
  });
});
