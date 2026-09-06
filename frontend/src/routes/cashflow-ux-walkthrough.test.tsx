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
  CATEGORIES: ["FOOD_AND_DRINK", "UNCATEGORIZED"],
  getOverviewSummary: vi.fn(),
  getCashflowTrend: vi.fn(),
  getCategoryComparison: vi.fn(),
  getTransactions: vi.fn(),
  getSpendingSummary: vi.fn(),
  getCumulativeSpending: vi.fn(),
  getCategoryCatalog: vi.fn(),
  patchTransactionAnnotation: vi.fn(),
}));

import * as api from "@/lib/api/client";
import OverviewPage from "./index";
import SpendingPage from "./spending";

const transaction = {
  id: 42,
  date: "2024-03-08",
  amount: 777,
  name: "ODD CHARGE 4821",
  merchant_name: null,
  effective_merchant: "Odd Charge",
  effective_account_name: "Card ··1234",
  pending: false,
  plaid_category_primary: "UNCATEGORIZED",
  plaid_category_detailed: null,
  plaid_category_friendly: "Uncategorized",
  effective_category: "UNCATEGORIZED",
  category_source: "plaid" as const,
  is_transfer: false,
  refund_status: null,
  annotation: { reviewed: false },
};

let host: HTMLDivElement;
let root: Root;

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function mount(page: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  root = createRoot(host);
  act(() => {
    root.render(<QueryClientProvider client={client}>{page}</QueryClientProvider>);
  });
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2024-03-15T12:00:00Z"));
  host = document.createElement("div");
  document.body.appendChild(host);
  window.history.replaceState({}, "", "/vibeledger/frontend/");

  vi.mocked(api.getOverviewSummary).mockResolvedValue({
    asOfDate: "2024-03-15",
    netWorth: 2500,
    assets: 3000,
    liabilities: 500,
    monthSpend: 2397,
    previousMonthSpend: 1580,
    monthIncome: 3000,
    previousMonthIncome: 3000,
    netCashflow: 603,
    previousNetCashflow: 1420,
    needsAttention: {
      unreviewedTransactions: 1,
      uncategorizedTransactions: 1,
      likelyRefunds: 0,
      transferPairsPending: 1,
    },
  });
  vi.mocked(api.getCashflowTrend).mockResolvedValue([]);
  vi.mocked(api.getCategoryComparison).mockResolvedValue([
    { category: "FOOD_AND_DRINK", current: 120, previous: 80 },
  ]);
  vi.mocked(api.getTransactions).mockResolvedValue({ total: 1, items: [transaction] });
  vi.mocked(api.getSpendingSummary).mockImplementation(async (args) => {
    const granularity = args?.granularity ?? "monthly";
    return {
    periodLabel: granularity === "yearly" ? "2024 YTD" : "March 2024",
    total: granularity === "yearly" ? 2477 : 2397,
    previousTotal: granularity === "yearly" ? 0 : 1580,
    change: granularity === "yearly" ? 2477 : 817,
    changePct: granularity === "yearly" ? null : 51.7,
    projection: granularity === "yearly" ? 6130 : 4954,
      topDriver: { category: "HOUSING", amount: 1500 },
    };
  });
  vi.mocked(api.getCumulativeSpending).mockResolvedValue([]);
  vi.mocked(api.getCategoryCatalog).mockResolvedValue([]);
  vi.mocked(api.patchTransactionAnnotation).mockResolvedValue({ status: "ok", transaction_id: 42 });
});

afterEach(() => {
  act(() => root?.unmount());
  host.remove();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("CF-03 synthetic cashflow walkthrough", () => {
  it("renders spending comparison and a bounded attention drill-down on the overview", async () => {
    mount(<OverviewPage />);
    await settle();

    expect(host.textContent).toContain("Month spend");
    expect(host.textContent).toContain("$2,397.0");
    expect(host.textContent).toContain("This month vs last month by category");
    expect(host.textContent).toContain("Uncategorized");
    expect(host.querySelector('a[href$="/transactions?filter=uncategorized"]')).not.toBeNull();
  });

  it("switches monthly spending to yearly and keeps the questionable row editable", async () => {
    window.history.replaceState({}, "", "/vibeledger/frontend/spending");
    mount(<SpendingPage />);
    await settle();

    expect(host.textContent).toContain("March 2024");
    const yearly = [...host.querySelectorAll("button")].find((node) => node.textContent === "yearly");
    expect(yearly).toBeDefined();
    await act(async () => yearly!.click());
    await settle();
    expect(api.getSpendingSummary).toHaveBeenCalledWith({ granularity: "yearly" });
    expect(host.textContent).toContain("2024 YTD");

    const row = [...host.querySelectorAll("button")].find((node) =>
      node.textContent?.includes("Odd Charge"),
    );
    expect(row).toBeDefined();
    await act(async () => row!.click());
    expect(host.querySelector('[role="dialog"][aria-label="Edit transaction"]')).not.toBeNull();
    expect(host.textContent).toContain("Original (from bank)");
    expect(host.textContent).toContain("Current mapping");

    const reviewed = host.querySelector('input[type="checkbox"]') as HTMLInputElement;
    await act(async () => reviewed.click());
    const save = [...host.querySelectorAll("button")].find((node) => node.textContent === "Save");
    await act(async () => save!.click());
    await settle();
    expect(api.patchTransactionAnnotation).toHaveBeenCalledWith(
      42,
      expect.objectContaining({ reviewed: true }),
    );
  });
});
