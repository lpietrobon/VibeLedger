// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/finance/charts/CashflowChart", () => ({
  default: () => <div>Cashflow chart</div>,
}));
vi.mock("@/components/finance/charts/CategoryBarChart", () => ({
  default: () => <div>Category chart</div>,
}));
vi.mock("@/components/finance/charts/CumulativeChart", () => ({
  default: () => <div>Cumulative chart</div>,
}));

vi.mock("@/lib/api/client", () => ({
  CATEGORIES: ["FOOD/OTHER", "FOOD/DINING", "SHOPPING/GENERAL"],
  CATEGORY_GROUPS: [{ label: "Food", options: ["FOOD/OTHER", "FOOD/DINING"] }],
  getOverviewSummary: vi.fn(),
  getCashflowTrend: vi.fn(),
  getCategoryComparison: vi.fn(),
  getTransactions: vi.fn(),
  getSpendingSummary: vi.fn(),
  getCumulativeSpending: vi.fn(),
  getCategoryCatalog: vi.fn(),
  syncAllAccounts: vi.fn(),
  patchTransactionAnnotation: vi.fn(),
  patchTransactionAnnotations: vi.fn(),
  getDuplicateCorrections: vi.fn(),
  createDuplicateCorrection: vi.fn(),
  reverseDuplicateCorrection: vi.fn(),
}));

vi.mock("@/lib/api/cache", () => ({
  invalidateLedger: vi.fn(async () => undefined),
}));

import * as api from "@/lib/api/client";
import OverviewPage from "./index";
import SpendingPage from "./spending";
import TransactionsPage from "./transactions";

const BASE = import.meta.env.BASE_URL.replace(/\/+$/, "");
const BOUNDS = { startDate: "2032-04-01", endDate: "2032-04-30" };
const CATEGORY = "FOOD/OTHER";
const EXPECTED_HREF = `${BASE}/transactions?category=FOOD%2FOTHER&query=is%3Aspend&startDate=2032-04-01&endDate=2032-04-30&sort=date&order=desc`;

const reporting = {
  currency: "USD" as const,
  currencyStatus: "single" as const,
  currencies: ["USD"],
  historyCoverage: "unverified" as const,
  duplicateAccountCoverage: "unverified" as const,
  qualification: "Recorded activity only.",
  startDate: BOUNDS.startDate,
  endDate: BOUNDS.endDate,
  recordedRowCount: 10,
  firstRecordedDate: BOUNDS.startDate,
  lastRecordedDate: BOUNDS.endDate,
  reportingDate: BOUNDS.endDate,
  currentPeriod: {
    currency: "USD" as const,
    currencyStatus: "single" as const,
    currencies: ["USD"],
    historyCoverage: "unverified" as const,
    duplicateAccountCoverage: "unverified" as const,
    qualification: "Recorded activity only.",
    startDate: BOUNDS.startDate,
    endDate: BOUNDS.endDate,
    recordedRowCount: 10,
    firstRecordedDate: BOUNDS.startDate,
    lastRecordedDate: BOUNDS.endDate,
  },
  previousPeriod: {
    currency: "USD" as const,
    currencyStatus: "single" as const,
    currencies: ["USD"],
    historyCoverage: "unverified" as const,
    duplicateAccountCoverage: "unverified" as const,
    qualification: "Recorded activity only.",
    startDate: "2032-03-01",
    endDate: "2032-03-31",
    recordedRowCount: 1,
    firstRecordedDate: "2032-03-01",
    lastRecordedDate: "2032-03-01",
  },
  comparisonAvailable: true,
  comparisonQualification: "Comparison of recorded activity only.",
  projectionQualification: "Recorded activity only.",
};

const activityRows = [
  { id: 105, date: "2032-04-06", amount: 12, name: "candidate-out", effective_category: CATEGORY },
  { id: 103, date: "2032-04-04", amount: -10, name: "food-refund", effective_category: CATEGORY },
  { id: 102, date: "2032-04-03", amount: 25, name: "food-charge-2", effective_category: CATEGORY },
  { id: 101, date: "2032-04-02", amount: 40, name: "food-charge-1", effective_category: CATEGORY },
].map((row) => ({
  ...row,
  merchant_name: row.name,
  effective_merchant: row.name,
  effective_account_name: "PI13 Card ··1314",
  pending: false,
  plaid_category_primary: "FOOD_AND_DRINK",
  plaid_category_detailed: null,
  plaid_category_friendly: "Food",
  category_source: "manual" as const,
  is_transfer: false,
  is_transfer_candidate: row.id === 105,
  transfer_pair_id: row.id === 105 ? 501 : null,
  refund_status: row.id === 103 ? "confirmed" as const : null,
  refund_match_transaction_id: row.id === 103 ? 102 : null,
  annotation: { reviewed: true },
}));

let host: HTMLDivElement;
let root: Root;

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function mount(page: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  root = createRoot(host);
  act(() => {
    root.render(<QueryClientProvider client={queryClient}>{page}</QueryClientProvider>);
  });
}

function categoryLink() {
  return [...host.querySelectorAll<HTMLAnchorElement>("a")].find(
    (link) => link.textContent?.trim() === CATEGORY,
  );
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2032-04-15T12:00:00Z"));
  host = document.createElement("div");
  document.body.appendChild(host);
  window.history.replaceState({}, "", `${BASE}/`);

  vi.mocked(api.getOverviewSummary).mockResolvedValue({
    asOfDate: BOUNDS.endDate,
    reporting,
    netWorth: 1000,
    assets: 1500,
    liabilities: 500,
    monthSpend: 67,
    previousMonthSpend: 30,
    monthIncome: 12,
    previousMonthIncome: 0,
    netCashflow: -55,
    previousNetCashflow: -30,
    needsAttention: { unreviewedTransactions: 0, uncategorizedTransactions: 0, likelyRefunds: 1, transferPairsPending: 1 },
  });
  vi.mocked(api.getCashflowTrend).mockResolvedValue([]);
  vi.mocked(api.getCategoryComparison).mockResolvedValue([
    { category: CATEGORY, current: 67, previous: 30 },
    { category: "SHOPPING/GENERAL", current: 17, previous: 0 },
  ]);
  vi.mocked(api.getSpendingSummary).mockResolvedValue({
    reporting,
    periodLabel: "April 2032",
    total: 67,
    previousTotal: 30,
    change: 37,
    changePct: 123.33,
    projection: 134,
    topDriver: { category: CATEGORY, amount: 67 },
  });
  vi.mocked(api.getCumulativeSpending).mockResolvedValue([]);
  vi.mocked(api.getCategoryCatalog).mockResolvedValue([]);
  vi.mocked(api.getTransactions).mockResolvedValue({ total: activityRows.length, items: activityRows });
  vi.mocked(api.getDuplicateCorrections).mockResolvedValue({ items: [] });
  vi.mocked(api.syncAllAccounts).mockResolvedValue({ results: [], summary: "1/1 item synced" });
});

afterEach(() => {
  act(() => root?.unmount());
  host.remove();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("PI-13 frozen category drilldown contract", () => {
  it("requires Overview and Spending to expose the same literal category destination", async () => {
    mount(<OverviewPage />);
    await settle();
    await settle();

    const overviewLink = categoryLink();
    expect(overviewLink, "Overview category aggregates must be inspectable").not.toBeNull();
    expect(overviewLink?.getAttribute("href")).toBe(EXPECTED_HREF);
    expect(overviewLink?.tabIndex).toBe(0);

    act(() => root.unmount());
    window.history.replaceState({}, "", `${BASE}/spending`);
    mount(<SpendingPage />);
    await settle();
    await settle();
    expect(categoryLink()?.getAttribute("href")).toBe(EXPECTED_HREF);
  });

  it("hydrates Activity through the destination and requests the exact spend population", async () => {
    window.history.replaceState({}, "", EXPECTED_HREF);
    mount(<TransactionsPage />);
    await settle();
    await settle();

    expect(api.getTransactions).toHaveBeenCalledWith({
      query: "is:spend",
      category: CATEGORY,
      startDate: BOUNDS.startDate,
      endDate: BOUNDS.endDate,
      limit: 500,
    });
    expect(host.textContent).toContain("candidate-out");
    expect(host.textContent).toContain("food-refund");
    expect(host.textContent).toContain("food-charge-2");
    expect(host.textContent).toContain("food-charge-1");
    expect((host.querySelector('input[aria-label="Start date"]') as HTMLInputElement).value)
      .toBe(BOUNDS.startDate);
    expect((host.querySelector('input[aria-label="End date"]') as HTMLInputElement).value)
      .toBe(BOUNDS.endDate);
    expect((host.querySelector('select[aria-label="Sort transactions"]') as HTMLSelectElement).value)
      .toBe("date:desc");
  });
});
