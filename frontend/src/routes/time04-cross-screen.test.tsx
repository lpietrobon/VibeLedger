// @vitest-environment jsdom
// TIME-04: real routes/controls, stubbed I/O; literal oracles independent of helpers.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@/components/layout/AppShell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
vi.mock("@/lib/accountScope", () => ({ useAccountScope: () => [[]], useAccountScopeQuery: () => "" }));
vi.mock("@/lib/api/client", async (original) => {
 const actual = await original<typeof import("@/lib/api/client")>();
 return { ...actual, ...Object.fromEntries(["getOverviewSummary", "getCashflowTrend", "getCategoryComparison", "getTransactions", "getSpendingSummary", "getCumulativeSpending", "getCategoryComparisonPeriod", "getSpendingTimeline", "getSpendingDay", "getCashflowSankey", "getCategoryMovers", "getDuplicateCorrections"].map(name => [name, vi.fn(() => new Promise<never>(() => {}))])) };
});
import * as api from "@/lib/api/client";
import Overview from "./index";
import Spending from "./spending";
import Insights from "./insights";
import Transactions from "./transactions";
const pages = [
 { name: "Overview", path: "/", Component: Overview, request: api.getOverviewSummary },
 { name: "Spending", path: "/spending", Component: Spending, request: api.getSpendingSummary },
 { name: "Insights", path: "/insights", Component: Insights, request: api.getCashflowSankey },
 { name: "Activity", path: "/transactions", Component: Transactions, request: api.getTransactions },
];
const base = import.meta.env.BASE_URL.replace(/\/+$/, "");
let host: HTMLDivElement; let root: Root;
async function settle() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); }); }
async function mount(Component: () => ReactNode) {
 const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
 root = createRoot(host);
 await act(async () => root.render(<QueryClientProvider client={client}><Component /></QueryClientProvider>));
 await settle();
}
function params(request: unknown) { return vi.mocked(request as typeof api.getOverviewSummary).mock.calls.at(-1)?.[0]; }
function change(selector: string, value: string) {
 const control = host.querySelector(selector) as HTMLInputElement;
 expect(control, selector).not.toBeNull();
 act(() => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(control, value);
  control.dispatchEvent(new Event("input", { bubbles: true }));
 });
}
beforeEach(() => {
 Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
 vi.useFakeTimers({ shouldAdvanceTime: true }); vi.setSystemTime(new Date("2026-10-25T12:00:00Z"));
 vi.clearAllMocks(); vi.mocked(api.getTransactions).mockImplementation(() => new Promise<never>(() => {})); window.localStorage.clear();
 host = document.createElement("div"); document.body.appendChild(host);
});
afterEach(() => { if (root) act(() => root.unmount()); host.remove(); vi.useRealTimers(); });
for (const page of pages) describe(page.name, () => {
 it("restores literal legacy bookmarked bounds and unrelated query parameters", async () => {
  window.history.replaceState({}, "", `${base}${page.path}?startDate=2020-03-05&endDate=2020-03-17&comparison=none&source=legacy&query=is%3Aspend&sort=amount&order=asc`);
  await mount(page.Component);
  expect(params(page.request)).toMatchObject({ startDate: "2020-03-05", endDate: "2020-03-17" });
  expect(new URLSearchParams(location.search).get("source")).toBe("legacy");
  expect(host.textContent).toContain("2020-03-05");
  if (page.name === "Overview" || page.name === "Spending") expect(params(page.request)?.compareStartDate).toBeUndefined();
  if (page.name === "Activity") expect(params(page.request)).toMatchObject({ query: "is:spend", sort: "amount", order: "asc" });
 });
 it("responds to browser back/forward navigation while already mounted", async () => {
  window.history.replaceState({}, "", `${base}${page.path}?startDate=2020-03-05&endDate=2020-03-17&comparison=none`);
  await mount(page.Component);
  await act(async () => {
   window.history.pushState({}, "", `${base}${page.path}?startDate=2024-02-29&endDate=2024-03-04&comparison=none`);
   window.dispatchEvent(new PopStateEvent("popstate"));
  });
  await settle();
  expect(params(page.request)).toMatchObject({ startDate: "2024-02-29", endDate: "2024-03-04" });
 });
 it.each(["startDate=2020-03-05", "startDate=2020-03-17&endDate=2020-03-05", "startDate=2023-02-29&endDate=2023-03-04"])("does not request an invalid bookmark %s", async (query) => {
  window.history.replaceState({}, "", `${base}${page.path}?${query}`); await mount(page.Component);
  expect(page.request).not.toHaveBeenCalled();
 });
 it("persists keyboard-editable custom bounds across remount", async () => {
  window.history.replaceState({}, "", `${base}${page.path}?source=retained`); await mount(page.Component);
  change('input[aria-label="From date"]', "2020-03-05"); change('input[aria-label="To date"]', "2020-03-17"); await settle();
  const url = new URLSearchParams(location.search);
  expect(url.get("startDate")).toBe("2020-03-05"); expect(url.get("endDate")).toBe("2020-03-17"); expect(url.get("source")).toBe("retained");
  act(() => root.unmount()); await mount(page.Component);
  expect(params(page.request)).toMatchObject({ startDate: "2020-03-05", endDate: "2020-03-17" });
 });
});
it("Insights None suppresses movers and preserves Sankey/heatmap bounds", async () => {
 window.history.replaceState({}, "", `${base}/insights?startDate=2020-03-05&endDate=2020-03-17&comparison=none`); await mount(Insights);
 expect(api.getCategoryMovers).not.toHaveBeenCalled();
 for (const request of [api.getCashflowSankey, api.getSpendingTimeline]) expect(params(request)).toMatchObject({startDate:"2020-03-05",endDate:"2020-03-17"});
});
it("Spending shares exact dates across summary, category, pace, timeline and Activity", async () => {
 window.history.replaceState({}, "", `${base}/spending?startDate=2020-03-05&endDate=2020-03-17&comparison=previous-year`); await mount(Spending);
 for (const request of [api.getSpendingSummary, api.getCumulativeSpending, api.getSpendingTimeline, api.getTransactions]) expect(params(request)).toMatchObject({ startDate: "2020-03-05", endDate: "2020-03-17" });
 expect(vi.mocked(api.getCategoryComparisonPeriod).mock.calls.at(-1)?.[2]).toMatchObject({startDate:"2020-03-05",endDate:"2020-03-17",compareStartDate:"2019-03-05",compareEndDate:"2019-03-17"});
 expect(params(api.getSpendingSummary)).toMatchObject({compareStartDate:"2019-03-05",compareEndDate:"2019-03-17"});
});
for (const page of pages) {
 it.each([
  ["Month", "2026-10-01", "2026-10-25"], ["Year", "2026-01-01", "2026-10-25"],
  ["30D", "2026-09-26", "2026-10-25"], ["1Y", "2025-10-26", "2026-10-25"],
 ])(`${page.name} narrow-screen preset %s requests literal bounds`, async (label, startDate, endDate) => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
  window.history.replaceState({}, "", `${base}${page.path}`); await mount(page.Component);
  const button = host.querySelector(`button[aria-label="${label} period"]`) as HTMLButtonElement;
  expect(button).not.toBeNull(); act(() => button.click()); await settle();
  expect(params(page.request)).toMatchObject({ startDate, endDate });
  expect((host.querySelector('input[aria-label="From date"]') as HTMLInputElement).value).toBe(startDate);
  expect((host.querySelector('input[aria-label="To date"]') as HTMLInputElement).value).toBe(endDate);
 });
}
for (const page of pages.slice(0, 3)) {
 it.each([
  ["previous-month", "2020-02-05", "2020-02-17"],
  ["previous-year", "2019-03-05", "2019-03-17"],
  ["previous-period", "2020-02-21", "2020-03-04"],
 ])(`${page.name} restores independent %s comparison with literal inclusive bounds`, async (rule, compareStartDate, compareEndDate) => {
  window.history.replaceState({}, "", `${base}${page.path}?startDate=2020-03-05&endDate=2020-03-17&comparison=${rule}`);
  await mount(page.Component);
  const request = page.name === "Insights" ? api.getCategoryMovers : page.request;
  expect(params(request)).toMatchObject({ startDate: "2020-03-05", endDate: "2020-03-17", compareStartDate, compareEndDate });
  expect(host.textContent).toContain(compareStartDate); expect(host.textContent).toContain(compareEndDate);
 });
}
it("Activity can reach evidence beyond the first 500 matching rows without losing date scope", async () => {
 const rows = Array.from({ length: 501 }, (_, index) => ({
  id: index + 1, date: "2020-03-10", amount: 1, name: index === 500 ? "TIME04 final evidence" : `Evidence ${index}`,
  effective_merchant: index === 500 ? "TIME04 final evidence" : `Evidence ${index}`,
  merchant_name: null, effective_category: "FOOD/OTHER", effective_account_name: "Synthetic checking",
  pending: false, is_transfer: false, is_transfer_candidate: false, annotation: { reviewed: true },
 }));
 vi.mocked(api.getTransactions).mockImplementation(async (query) => ({
  items: rows.slice(query?.offset ?? 0, (query?.offset ?? 0) + (query?.limit ?? 100)), total: 501,
 }) as Awaited<ReturnType<typeof api.getTransactions>>);
 window.history.replaceState({}, "", `${base}/transactions?startDate=2020-03-05&endDate=2020-03-17&query=is%3Aspend`);
 await mount(Transactions); await settle();
 // Either automatic complete pagination or an accessible explicit next/load-more control is valid.
 for (let i = 0; i < 6 && !host.textContent?.includes("TIME04 final evidence"); i++) {
  const next = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => /next|load more|show more/i.test(`${b.textContent} ${b.getAttribute("aria-label") ?? ""}`) && !b.disabled);
  if (!next) break;
  act(() => next.click()); await settle(); await settle();
 }
 expect(host.textContent).toContain("TIME04 final evidence");
 expect(vi.mocked(api.getTransactions).mock.calls.every(([query]) => query?.startDate === "2020-03-05" && query?.endDate === "2020-03-17" && query?.query?.includes("is:spend"))).toBe(true);
}, 30000);
for (const page of pages.slice(0, 3)) it(`${page.name} persists independent comparator choice without changing selected dates`, async () => {
 window.history.replaceState({}, "", `${base}${page.path}?startDate=2020-03-05&endDate=2020-03-17&comparison=none`);
 await mount(page.Component);
 const select = host.querySelector('select[aria-label="Comparison rule"]') as HTMLSelectElement;
 expect(select).not.toBeNull();
 act(() => { select.value = "previous-year"; select.dispatchEvent(new Event("change", { bubbles: true })); }); await settle();
 expect(new URLSearchParams(location.search).get("comparison")).toBe("previous-year");
 expect(params(page.request)).toMatchObject({startDate:"2020-03-05",endDate:"2020-03-17"});
});
it("Overview selected flow and evidence requests share exact dates while current snapshot remains separate", async () => {
 window.history.replaceState({}, "", `${base}/?startDate=2020-03-05&endDate=2020-03-17&comparison=none`); await mount(Overview);
 for (const request of [api.getOverviewSummary, api.getCashflowTrend, api.getTransactions]) expect(params(request)).toMatchObject({startDate:"2020-03-05",endDate:"2020-03-17"});
 expect(vi.mocked(api.getCategoryComparison).mock.calls.at(-1)?.[1]).toMatchObject({startDate:"2020-03-05",endDate:"2020-03-17"});
});
