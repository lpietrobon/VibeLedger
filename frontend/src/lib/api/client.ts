import type {
  OverviewSummary,
  CashflowPoint,
  CategorySpendPoint,
  CategoryComparisonPoint,
  AccountSummary,
  Transaction,
  TransactionsResponse,
  SpendingSummary,
  CumulativeSpendingPoint,
  CategoryRule,
  TransfersResponse,
} from "./types";
import { CATEGORY_COLORS } from "./mock-data";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/vibeledger/api";
const MAX_PAGE_SIZE = 500;

type MonthlySpendRow = {
  month: string;
  spend: number;
};

const jsonFetch = async <T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  init?: RequestInit,
) => {
  const url = new URL(path.replace(/^\/+/, ""), apiOrigin());
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }

  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} from ${url.pathname}`);
  }
  return response.json() as Promise<T>;
};

function apiOrigin() {
  if (/^https?:\/\//.test(API_BASE)) return API_BASE.endsWith("/") ? API_BASE : `${API_BASE}/`;
  return new URL(API_BASE.replace(/^\//, "") + "/", window.location.origin + "/");
}

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function dateKey(d: Date) {
  return `${monthKey(d)}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseMonth(month: string) {
  const [year, index] = month.split("-").map(Number);
  return new Date(year, index - 1, 1);
}

function addMonths(d: Date, months: number) {
  return new Date(d.getFullYear(), d.getMonth() + months, 1);
}

function monthBounds(month: string) {
  const start = parseMonth(month);
  const end = new Date(start.getFullYear(), start.getMonth() + 1, 0);
  return { startDate: dateKey(start), endDate: dateKey(end) };
}

function yearBounds(year: number) {
  return { start: `${year}-01-01`, end: `${year}-12-31` };
}

function currentMonth() {
  return monthKey(new Date());
}

function previousMonth(month = currentMonth()) {
  return monthKey(addMonths(parseMonth(month), -1));
}

function latestMonth(rows: Array<{ month: string }>, fallback = currentMonth()) {
  return rows.length ? rows[rows.length - 1].month : fallback;
}

function sumSpend(items: Transaction[]) {
  return items.reduce((sum, t) => sum + (t.amount > 0 || isRefund(t) ? t.amount : 0), 0);
}

function isRefund(t: Transaction) {
  return t.refund_status === "confirmed" || t.refund_status === "likely";
}

function pctChange(current: number, previous: number) {
  if (!previous) return null;
  return ((current - previous) / previous) * 100;
}

function formatPeriodLabel(granularity: "monthly" | "yearly", period: string | number) {
  if (granularity === "yearly") return `${period} YTD`;
  return parseMonth(String(period)).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

async function getMonthlySpend(params?: {
  startDate?: string;
  endDate?: string;
}): Promise<MonthlySpendRow[]> {
  return jsonFetch<MonthlySpendRow[]>("/analytics/monthly-spend", {
    start_date: params?.startDate,
    end_date: params?.endDate,
  });
}

async function getAllTransactions(params?: {
  startDate?: string;
  endDate?: string;
  category?: string;
}): Promise<Transaction[]> {
  const first = await getTransactions({ ...params, limit: MAX_PAGE_SIZE, offset: 0 });
  return first.items;
}

export async function getOverviewSummary(): Promise<OverviewSummary> {
  const [accounts, cashflow, transactions, transfers] = await Promise.all([
    getAccountsSummary(),
    getCashflowTrend(),
    getTransactions({ limit: MAX_PAGE_SIZE }),
    getTransfers(),
  ]);

  const month = latestMonth(cashflow);
  const previous = previousMonth(month);
  const byMonth = new Map(cashflow.map((row) => [row.month, row]));
  const currentFlow = byMonth.get(month);
  const previousFlow = byMonth.get(previous);
  const items = transactions.items;

  return {
    asOfDate: items[0]?.date ?? new Date().toISOString().slice(0, 10),
    netWorth: accounts.net_worth,
    assets: accounts.assets,
    liabilities: accounts.liabilities,
    monthSpend: currentFlow?.expenses ? Math.abs(currentFlow.expenses) : 0,
    previousMonthSpend: previousFlow?.expenses ? Math.abs(previousFlow.expenses) : 0,
    monthIncome: currentFlow?.income ?? 0,
    previousMonthIncome: previousFlow?.income ?? 0,
    netCashflow: currentFlow?.net ?? 0,
    previousNetCashflow: previousFlow?.net ?? 0,
    needsAttention: {
      unreviewedTransactions: items.filter((t) => !t.annotation.reviewed).length,
      uncategorizedTransactions: items.filter((t) => t.effective_category.toLowerCase() === "uncategorized").length,
      likelyRefunds: items.filter((t) => t.refund_status === "likely").length,
      transferPairsPending: transfers.items.filter((t) => !t.confirmed).length,
    },
  };
}

export async function getCashflowTrend(): Promise<CashflowPoint[]> {
  const rows = await jsonFetch<Array<{ month: string; income: number; expenses: number; net: number }>>(
    "/analytics/cashflow-trend",
  );
  return rows.slice(-12).map((row) => ({
    month: row.month,
    income: row.income,
    expenses: -Math.abs(row.expenses),
    net: row.net,
  }));
}

export async function getCategorySpend(params?: {
  startDate?: string;
  endDate?: string;
}): Promise<CategorySpendPoint[]> {
  const rows = await jsonFetch<CategorySpendPoint[]>("/analytics/category-spend", {
    start_date: params?.startDate,
    end_date: params?.endDate,
  });
  return rows
    .filter((row) => row.spend > 0)
    .map((row) => ({ ...row, color: CATEGORY_COLORS[row.category] }))
    .sort((a, b) => b.spend - a.spend);
}

export async function getCategoryComparison(): Promise<CategoryComparisonPoint[]> {
  const monthly = await getMonthlySpend();
  const current = latestMonth(monthly);
  const previous = previousMonth(current);
  const [currentRows, previousRows] = await Promise.all([
    getCategorySpend(monthBounds(current)),
    getCategorySpend(monthBounds(previous)),
  ]);
  const categories = new Set([...currentRows, ...previousRows].map((row) => row.category));
  return Array.from(categories)
    .map((category) => ({
      category,
      current: currentRows.find((row) => row.category === category)?.spend ?? 0,
      previous: previousRows.find((row) => row.category === category)?.spend ?? 0,
    }))
    .sort((a, b) => b.current - a.current);
}

export async function getAccountsSummary(): Promise<AccountSummary> {
  return jsonFetch<AccountSummary>("/analytics/accounts-summary");
}

export async function patchAccountNickname(
  accountId: number,
  payload: { nickname: string | null },
): Promise<{ status: "ok"; account_id: number }> {
  return jsonFetch<{ status: "ok"; account_id: number }>(`/accounts/${accountId}`, undefined, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getTransactions(params?: {
  startDate?: string;
  endDate?: string;
  category?: string;
  limit?: number;
  offset?: number;
  query?: string;
}): Promise<TransactionsResponse> {
  const response = await jsonFetch<TransactionsResponse>("/transactions", {
    start_date: params?.startDate,
    end_date: params?.endDate,
    category: params?.category && params.category !== "All" ? params.category : undefined,
    limit: params?.limit ?? 100,
    offset: params?.offset ?? 0,
  });

  if (!params?.query) return response;

  const q = params.query.toLowerCase();
  const items = response.items.filter(
    (t) =>
      t.name.toLowerCase().includes(q) ||
      (t.effective_merchant ?? "").toLowerCase().includes(q) ||
      (t.merchant_name ?? "").toLowerCase().includes(q) ||
      t.effective_category.toLowerCase().includes(q),
  );
  return { total: items.length, items };
}

export async function getSpendingSummary(params?: {
  granularity: "monthly" | "yearly";
}): Promise<SpendingSummary> {
  const granularity = params?.granularity ?? "monthly";
  const monthly = await getMonthlySpend();
  const current = latestMonth(monthly);

  if (granularity === "yearly") {
    const year = parseMonth(current).getFullYear();
    const previousYear = year - 1;
    const currentRows = monthly.filter((row) => row.month.startsWith(`${year}-`));
    const previousRows = monthly.filter((row) => row.month.startsWith(`${previousYear}-`));
    const total = currentRows.reduce((sum, row) => sum + row.spend, 0);
    const previousTotal = previousRows.reduce((sum, row) => sum + row.spend, 0);
    const comparison = await getCategoryComparison();
    const topDriver = comparison[0]
      ? { category: comparison[0].category, amount: comparison[0].current - comparison[0].previous }
      : null;
    return {
      periodLabel: formatPeriodLabel("yearly", year),
      total,
      previousTotal,
      change: total - previousTotal,
      changePct: pctChange(total, previousTotal),
      projection: currentRows.length ? (total / currentRows.length) * 12 : 0,
      topDriver,
    };
  }

  const currentSpend = monthly.find((row) => row.month === current)?.spend ?? 0;
  const previous = previousMonth(current);
  const previousSpend = monthly.find((row) => row.month === previous)?.spend ?? 0;
  const comparison = await getCategoryComparison();
  const topDriver = comparison[0]
    ? { category: comparison[0].category, amount: comparison[0].current - comparison[0].previous }
    : null;

  return {
    periodLabel: formatPeriodLabel("monthly", current),
    total: currentSpend,
    previousTotal: previousSpend,
    change: currentSpend - previousSpend,
    changePct: pctChange(currentSpend, previousSpend),
    projection: projectMonthlySpend(current, currentSpend),
    topDriver,
  };
}

export async function getCumulativeSpending(params?: {
  granularity: "monthly" | "yearly";
}): Promise<CumulativeSpendingPoint[]> {
  const granularity = params?.granularity ?? "monthly";
  const monthly = await getMonthlySpend();
  const current = latestMonth(monthly);

  if (granularity === "yearly") {
    const year = parseMonth(current).getFullYear();
    const rows: CumulativeSpendingPoint[] = Array.from({ length: 12 }, (_, i) => ({
      day: i + 1,
      current: null,
      previous1: null,
      previous2: null,
      previous3: null,
    }));
    for (let offset = 0; offset <= 3; offset += 1) {
      let running = 0;
      const key = offset === 0 ? "current" : (`previous${offset}` as "previous1" | "previous2" | "previous3");
      const targetYear = year - offset;
      const lastDataMonthIndex = latestMonthIndex(monthly, targetYear);
      for (let i = 0; i < 12; i += 1) {
        if (lastDataMonthIndex === null || i > lastDataMonthIndex) {
          rows[i][key] = null;
          continue;
        }
        const row = monthly.find((r) => r.month === `${targetYear}-${String(i + 1).padStart(2, "0")}`);
        running += row?.spend ?? 0;
        rows[i][key] = running;
      }
    }
    return rows;
  }

  const periods = [current, previousMonth(current), previousMonth(previousMonth(current)), previousMonth(previousMonth(previousMonth(current)))];
  const txByPeriod = await Promise.all(periods.map((period) => getAllTransactions(monthBounds(period))));
  const daysInMonth = new Date(parseMonth(current).getFullYear(), parseMonth(current).getMonth() + 1, 0).getDate();
  const lastDays = txByPeriod.map(lastTransactionDay);
  return Array.from({ length: daysInMonth }, (_, i) => {
    const day = i + 1;
    return {
      day,
      current: cumulativeForDay(txByPeriod[0], day, lastDays[0]),
      previous1: cumulativeForDay(txByPeriod[1], day, lastDays[1]),
      previous2: cumulativeForDay(txByPeriod[2], day, lastDays[2]),
      previous3: cumulativeForDay(txByPeriod[3], day, lastDays[3]),
    };
  });
}

export async function patchTransactionAnnotation(
  transactionId: number,
  payload: {
    user_category?: string | null;
    merchant_name_override?: string | null;
    notes?: string | null;
    reviewed?: boolean;
    refund_status?: "confirmed" | "not_refund" | "auto" | null;
  },
): Promise<{ status: "ok"; transaction_id: number }> {
  return jsonFetch<{ status: "ok"; transaction_id: number }>(`/transactions/${transactionId}/annotation`, undefined, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function patchTransactionAnnotations(
  transactionIds: number[],
  payload: {
    user_category?: string | null;
    merchant_name_override?: string | null;
    notes?: string | null;
    reviewed?: boolean;
    refund_status?: "confirmed" | "not_refund" | "auto" | null;
  },
): Promise<{ status: "ok"; transaction_ids: number[]; updated: number }> {
  return jsonFetch<{ status: "ok"; transaction_ids: number[]; updated: number }>(
    "/transactions/annotations/batch",
    undefined,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_ids: transactionIds, ...payload }),
    },
  );
}

export async function getCategoryRules(): Promise<{ items: CategoryRule[] }> {
  return jsonFetch<{ items: CategoryRule[] }>("/category-rules");
}

export async function getTransfers(): Promise<TransfersResponse> {
  return jsonFetch<TransfersResponse>("/transfers", { limit: 1000 });
}

export async function syncAllAccounts(): Promise<{ results: unknown[]; summary: string }> {
  return jsonFetch<{ results: unknown[]; summary: string }>("/sync/all", undefined, {
    method: "POST",
  });
}

function projectMonthlySpend(month: string, spend: number) {
  const today = new Date();
  const parsed = parseMonth(month);
  const daysInMonth = new Date(parsed.getFullYear(), parsed.getMonth() + 1, 0).getDate();
  const elapsed =
    parsed.getFullYear() === today.getFullYear() && parsed.getMonth() === today.getMonth()
      ? today.getDate()
      : daysInMonth;
  return elapsed ? (spend / elapsed) * daysInMonth : spend;
}

function cumulativeForDay(items: Transaction[], day: number, lastDay: number | null) {
  if (lastDay === null || day > lastDay) return null;
  return items
    .filter((t) => Number(t.date.slice(8, 10)) <= day)
    .reduce((sum, t) => sum + (t.amount > 0 || isRefund(t) ? t.amount : 0), 0);
}

function lastTransactionDay(items: Transaction[]) {
  if (!items.length) return null;
  return Math.max(...items.map((t) => Number(t.date.slice(8, 10))));
}

function latestMonthIndex(rows: MonthlySpendRow[], year: number) {
  const monthIndexes = rows
    .filter((row) => row.month.startsWith(`${year}-`))
    .map((row) => Number(row.month.slice(5, 7)) - 1);
  return monthIndexes.length ? Math.max(...monthIndexes) : null;
}

export const CATEGORY_GROUPS = [
  {
    label: "Housing",
    options: ["HOUSING", "HOUSING/RENT_AND_UTILITIES", "HOUSING/UTILITIES"],
  },
  {
    label: "Food",
    options: ["FOOD", "FOOD/GROCERIES", "FOOD/DINING", "FOOD/COFFEE", "FOOD/OTHER"],
  },
  {
    label: "Transport",
    options: ["TRANSPORT", "TRANSPORT/RIDESHARE", "TRANSPORT/FUEL", "TRANSPORT/PARKING", "TRANSPORT/OTHER"],
  },
  {
    label: "Shopping",
    options: ["SHOPPING", "SHOPPING/GENERAL", "SHOPPING/CLOTHING", "SHOPPING/HOME", "SHOPPING/ELECTRONICS"],
  },
  {
    label: "Fun",
    options: ["FUN", "FUN/ENTERTAINMENT", "FUN/TRAVEL", "FUN/EVENTS"],
  },
  {
    label: "Health",
    options: ["HEALTH", "HEALTH/MEDICAL", "HEALTH/PERSONAL_CARE", "HEALTH/FITNESS"],
  },
  {
    label: "Finance",
    options: ["FINANCE", "FINANCE/LOANS", "FINANCE/FEES", "FINANCE/INVESTING"],
  },
  {
    label: "Income",
    options: ["INCOME", "INCOME/SALARY", "INCOME/INTEREST", "INCOME/REFUND", "INCOME/OTHER"],
  },
  {
    label: "Other",
    options: ["SERVICES/GENERAL", "SUBSCRIPTIONS", "UNCATEGORIZED"],
  },
];

export const CATEGORIES = CATEGORY_GROUPS.flatMap((group) => group.options);
