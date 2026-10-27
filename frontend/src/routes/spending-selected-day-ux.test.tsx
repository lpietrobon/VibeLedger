// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

vi.mock("@/components/finance/charts/CumulativeChart", () => ({
  default: ({ onSelect }: { onSelect: (day: string) => void }) =>
    <button type="button" onClick={() => onSelect("2026-10-10")}>Select cumulative point Oct 10</button>,
}));
vi.mock("@/lib/api/client", () => ({
  CATEGORIES: ["FOOD/OTHER", "INSURANCE"],
  getSpendingSummary: vi.fn(), getCategoryComparisonPeriod: vi.fn(),
  getCumulativeSpending: vi.fn(), getSpendingTimeline: vi.fn(), getSpendingDay: vi.fn(),
  getTransactions: vi.fn(), patchTransactionAnnotation: vi.fn(),
  getCategoryCatalog: vi.fn(),
}));
vi.mock("@/lib/api/cache", () => ({ invalidateLedger: vi.fn(async () => undefined) }));
import * as api from "@/lib/api/client";
import SpendingPage from "./spending";

let root: Root;
let container: HTMLDivElement;
const settled = async () => { await act(async () => { await new Promise((done) => setTimeout(done, 0)); }); };
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-10-25T12:00:00Z"));
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(api.getSpendingSummary).mockResolvedValue({
    reporting: { comparisonAvailable: true } as never,
    periodLabel: "October 2026", total: 4860, dailyAverage: 194,
    previousTotal: 4385, change: 475, changePct: 10.8, projection: 4860,
    topDriver: { category: "INSURANCE", amount: 850 },
  });
  vi.mocked(api.getCategoryComparisonPeriod).mockResolvedValue({
    items: [{category:"FOOD/OTHER",current:1420,previous:1200}],
    reporting: { comparisonAvailable: true } as never,
  });
  vi.mocked(api.getCumulativeSpending).mockResolvedValue([
    {day:10,date:"2026-10-10",current:2940,previous1:2400,previous2:2000,previous3:null},
    {day:11,date:"2026-10-11",current:3140,previous1:2600,previous2:2200,previous3:null},
  ]);
  vi.mocked(api.getSpendingTimeline).mockResolvedValue({
    start_date:"2026-10-01",end_date:"2026-10-25",
    days:[{date:"2026-10-10",amount:1200},{date:"2026-10-11",amount:200}],
    spikes:[],qualification:"",
  });
  vi.mocked(api.getSpendingDay).mockImplementation(async (day) => ({
    date: day, total: day === "2026-10-10" ? 1200 : 200,
    transaction_count:day === "2026-10-10" ? 6 : 1, qualification:"",
    items:day === "2026-10-10" ? [
      {id:1,merchant:"Insurance",amount:850,percent_of_day:70.8,cumulative_percent:70.8},
      {id:2,merchant:"Pharmacy",amount:150,percent_of_day:12.5,cumulative_percent:83.3},
      {id:3,merchant:"Grocery",amount:90,percent_of_day:7.5,cumulative_percent:90.8},
      {id:4,merchant:"Gas",amount:60,percent_of_day:5,cumulative_percent:95.8},
      {id:5,merchant:"Coffee",amount:50,percent_of_day:4.2,cumulative_percent:100},
    ] : [{id:6,merchant:"Other",amount:200,percent_of_day:100,cumulative_percent:100}],
  }));
  vi.mocked(api.getTransactions).mockResolvedValue({total:0,items:[]});
  vi.mocked(api.getCategoryCatalog).mockResolvedValue([]);
  window.history.replaceState({}, "", "/vibeledger/frontend/spending");
});
afterEach(() => { act(() => root.unmount()); container.remove(); vi.clearAllMocks(); vi.useRealTimers(); });

it("keeps four one-row KPIs, fixed default prior lines and a compact five-transaction detail for any tapped day", async () => {
  const client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  act(() => root.render(<QueryClientProvider client={client}><SpendingPage/></QueryClientProvider>));
  await settled(); await settled();
  expect(container.textContent).toContain("Top category");
  expect(container.textContent).toContain("Daily avg");
  expect(container.textContent).toContain("+10.8%");
  expect(api.getCumulativeSpending).toHaveBeenCalledWith(expect.objectContaining({
    startDate:"2026-10-01",endDate:"2026-10-25",
    comparisonPeriods:[
      {startDate:"2026-09-01",endDate:"2026-09-25"},
      {startDate:"2026-08-01",endDate:"2026-08-25"},
    ],
  }));
  await act(async () => (Array.from(container.querySelectorAll("button")).find(x =>
    x.textContent?.includes("Select cumulative point Oct 10")) as HTMLButtonElement).click());
  await settled();
  expect(api.getSpendingDay).toHaveBeenCalledWith("2026-10-10");
  expect(container.textContent).toContain("Insurance");
  expect(container.textContent).toContain("70.8%");
  expect(container.textContent).toContain("100%");
  expect(container.querySelectorAll("table tbody tr").length).toBe(5);
  expect(Array.from(container.querySelectorAll("a")).find(x =>
    x.textContent?.includes("Inspect all transactions for this day"))?.getAttribute("href"))
    .toContain("startDate=2026-10-10&endDate=2026-10-10");
  expect(container.textContent).not.toContain("Daily spending · investigate peaks");
  await act(async () => (container.querySelector('button[aria-label="0 prior periods"]') as HTMLButtonElement).click());
  await settled();
  expect(api.getCumulativeSpending).toHaveBeenCalledWith(expect.objectContaining({
    comparisonPeriods: [], compareStartDate: undefined,
  }));
  expect(container.textContent).toContain("+10.8%");
});
