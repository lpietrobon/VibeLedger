import type {
  OverviewSummary,
  CashflowPoint,
  CategorySpendPoint,
  CategoryComparisonPoint,
  AccountSummary,
  TransactionsResponse,
  SpendingSummary,
  CumulativeSpendingPoint,
  CategoryRule,
  CategoryRuleDraft,
  TransfersResponse,
  RecurringResponse,
  ConnectSession,
  ConnectStatus,
} from "./types";
import { CATEGORY_COLORS } from "./theme";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/vibeledger/api";
const MAX_PAGE_SIZE = 500;

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
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
};

const jsonBody = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function apiOrigin() {
  if (/^https?:\/\//.test(API_BASE)) return API_BASE.endsWith("/") ? API_BASE : `${API_BASE}/`;
  return new URL(API_BASE.replace(/^\//, "") + "/", window.location.origin + "/");
}

// --- Analytics (all computed server-side; the client only fetches + maps) ---

type OverviewResponse = {
  as_of_date: string;
  net_worth: number;
  assets: number;
  liabilities: number;
  month_spend: number;
  previous_month_spend: number;
  month_income: number;
  previous_month_income: number;
  net_cashflow: number;
  previous_net_cashflow: number;
  needs_attention: {
    unreviewed_transactions: number;
    uncategorized_transactions: number;
    likely_refunds: number;
    transfer_pairs_pending: number;
  };
};

export async function getOverviewSummary(): Promise<OverviewSummary> {
  const r = await jsonFetch<OverviewResponse>("/analytics/overview");
  return {
    asOfDate: r.as_of_date,
    netWorth: r.net_worth,
    assets: r.assets,
    liabilities: r.liabilities,
    monthSpend: r.month_spend,
    previousMonthSpend: r.previous_month_spend,
    monthIncome: r.month_income,
    previousMonthIncome: r.previous_month_income,
    netCashflow: r.net_cashflow,
    previousNetCashflow: r.previous_net_cashflow,
    needsAttention: {
      unreviewedTransactions: r.needs_attention.unreviewed_transactions,
      uncategorizedTransactions: r.needs_attention.uncategorized_transactions,
      likelyRefunds: r.needs_attention.likely_refunds,
      transferPairsPending: r.needs_attention.transfer_pairs_pending,
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

type SpendingSummaryResponse = {
  period_label: string;
  total: number;
  previous_total: number;
  change: number;
  change_pct: number | null;
  projection: number;
  top_driver: { category: string; amount: number } | null;
  category_comparison: CategoryComparisonPoint[];
};

async function fetchSpendingSummary(granularity: "monthly" | "yearly") {
  return jsonFetch<SpendingSummaryResponse>("/analytics/spending-summary", { granularity });
}

export async function getSpendingSummary(params?: {
  granularity: "monthly" | "yearly";
}): Promise<SpendingSummary> {
  const r = await fetchSpendingSummary(params?.granularity ?? "monthly");
  return {
    periodLabel: r.period_label,
    total: r.total,
    previousTotal: r.previous_total,
    change: r.change,
    changePct: r.change_pct,
    projection: r.projection,
    topDriver: r.top_driver,
  };
}

export async function getCategoryComparison(): Promise<CategoryComparisonPoint[]> {
  const r = await fetchSpendingSummary("monthly");
  return r.category_comparison.slice().sort((a, b) => b.current - a.current);
}

export async function getCumulativeSpending(params?: {
  granularity: "monthly" | "yearly";
}): Promise<CumulativeSpendingPoint[]> {
  const rows = await jsonFetch<
    Array<{ x: number; current: number | null; previous1: number | null; previous2: number | null; previous3: number | null }>
  >("/analytics/cumulative-spend", { granularity: params?.granularity ?? "monthly" });
  return rows.map((row) => ({
    day: row.x,
    current: row.current,
    previous1: row.previous1,
    previous2: row.previous2,
    previous3: row.previous3,
  }));
}

// --- Accounts ---

export async function getAccountsSummary(): Promise<AccountSummary> {
  return jsonFetch<AccountSummary>("/analytics/accounts-summary");
}

export async function patchAccountNickname(
  accountId: number,
  payload: { nickname: string | null },
): Promise<{ status: "ok"; account_id: number }> {
  return jsonFetch(`/accounts/${accountId}`, undefined, jsonBody("PATCH", payload));
}

// --- Transactions ---

export async function getTransactions(params?: {
  startDate?: string;
  endDate?: string;
  category?: string;
  limit?: number;
  offset?: number;
  query?: string;
}): Promise<TransactionsResponse> {
  return jsonFetch<TransactionsResponse>("/transactions", {
    start_date: params?.startDate,
    end_date: params?.endDate,
    category: params?.category && params.category !== "All" ? params.category : undefined,
    q: params?.query || undefined,
    limit: params?.limit ?? 100,
    offset: params?.offset ?? 0,
  });
}

type AnnotationPayload = {
  user_category?: string | null;
  merchant_name_override?: string | null;
  notes?: string | null;
  reviewed?: boolean;
  refund_status?: "confirmed" | "not_refund" | "auto" | null;
};

export async function patchTransactionAnnotation(
  transactionId: number,
  payload: AnnotationPayload,
): Promise<{ status: "ok"; transaction_id: number }> {
  return jsonFetch(`/transactions/${transactionId}/annotation`, undefined, jsonBody("PATCH", payload));
}

export async function patchTransactionAnnotations(
  transactionIds: number[],
  payload: AnnotationPayload,
): Promise<{ status: "ok"; transaction_ids: number[]; updated: number }> {
  return jsonFetch(
    "/transactions/annotations/batch",
    undefined,
    jsonBody("PATCH", { transaction_ids: transactionIds, ...payload }),
  );
}

// --- Category rules ---

export async function getCategoryRules(): Promise<{ items: CategoryRule[] }> {
  return jsonFetch<{ items: CategoryRule[] }>("/category-rules");
}

export async function createCategoryRule(payload: CategoryRuleDraft): Promise<CategoryRule> {
  return jsonFetch<CategoryRule>("/category-rules", undefined, jsonBody("POST", payload));
}

export async function patchCategoryRule(
  ruleId: number,
  payload: Partial<CategoryRuleDraft>,
): Promise<CategoryRule> {
  return jsonFetch<CategoryRule>(`/category-rules/${ruleId}`, undefined, jsonBody("PATCH", payload));
}

export async function deleteCategoryRule(ruleId: number): Promise<{ status: string; id: number }> {
  return jsonFetch(`/category-rules/${ruleId}`, undefined, { method: "DELETE" });
}

export async function previewCategoryRule(payload: {
  rule_id?: number;
  draft_rule?: CategoryRuleDraft;
}): Promise<{ total_scanned: number; would_change_count: number; samples: unknown[] }> {
  return jsonFetch("/category-rules/preview", undefined, jsonBody("POST", payload));
}

export async function applyCategoryRules(): Promise<{ updated_count: number; would_change_count: number }> {
  return jsonFetch("/category-rules/apply", undefined, jsonBody("POST", { dry_run: false }));
}

// --- Transfers ---

export async function getTransfers(): Promise<TransfersResponse> {
  return jsonFetch<TransfersResponse>("/transfers", { limit: 1000 });
}

export async function detectTransfers(): Promise<{ created: number; pair_ids: number[] }> {
  return jsonFetch("/transfers/detect", undefined, { method: "POST" });
}

export async function confirmTransfer(pairId: number): Promise<{ id: number; confirmed: boolean }> {
  return jsonFetch(`/transfers/${pairId}/confirm`, undefined, { method: "POST" });
}

export async function deleteTransfer(pairId: number): Promise<{ status: string }> {
  return jsonFetch(`/transfers/${pairId}`, undefined, { method: "DELETE" });
}

// --- Recurring ---

export async function getRecurring(params?: {
  status?: "active" | "inactive";
  minMonthly?: number;
}): Promise<RecurringResponse> {
  return jsonFetch<RecurringResponse>("/analytics/recurring", {
    status: params?.status,
    min_monthly: params?.minMonthly,
  });
}

export async function setRecurringStatus(
  merchantKey: string,
  status: "auto" | "kept" | "canceled",
): Promise<{ merchant_key: string; manual_status: string | null }> {
  return jsonFetch(
    `/analytics/recurring/${encodeURIComponent(merchantKey)}/status`,
    undefined,
    jsonBody("POST", { status }),
  );
}

// --- Connect / sync ---

export async function createConnectSession(): Promise<ConnectSession> {
  return jsonFetch<ConnectSession>("/connect/sessions", undefined, jsonBody("POST", { user_id: "default-user" }));
}

export async function getConnectStatus(sessionToken: string): Promise<ConnectStatus> {
  return jsonFetch<ConnectStatus>(`/connect/sessions/${sessionToken}`);
}

export async function syncAllAccounts(): Promise<{ results: unknown[]; summary: string }> {
  return jsonFetch("/sync/all", undefined, { method: "POST" });
}

export { MAX_PAGE_SIZE };

export const CATEGORY_GROUPS = [
  { label: "Housing", options: ["HOUSING", "HOUSING/RENT_AND_UTILITIES", "HOUSING/UTILITIES"] },
  { label: "Food", options: ["FOOD", "FOOD/GROCERIES", "FOOD/DINING", "FOOD/COFFEE", "FOOD/OTHER"] },
  { label: "Transport", options: ["TRANSPORT", "TRANSPORT/RIDESHARE", "TRANSPORT/FUEL", "TRANSPORT/PARKING", "TRANSPORT/OTHER"] },
  { label: "Shopping", options: ["SHOPPING", "SHOPPING/GENERAL", "SHOPPING/CLOTHING", "SHOPPING/HOME", "SHOPPING/ELECTRONICS"] },
  { label: "Fun", options: ["FUN", "FUN/ENTERTAINMENT", "FUN/TRAVEL", "FUN/EVENTS"] },
  { label: "Health", options: ["HEALTH", "HEALTH/MEDICAL", "HEALTH/PERSONAL_CARE", "HEALTH/FITNESS"] },
  { label: "Finance", options: ["FINANCE", "FINANCE/LOANS", "FINANCE/FEES", "FINANCE/INVESTING"] },
  { label: "Income", options: ["INCOME", "INCOME/SALARY", "INCOME/INTEREST", "INCOME/REFUND", "INCOME/OTHER"] },
  { label: "Other", options: ["SERVICES/GENERAL", "SUBSCRIPTIONS", "UNCATEGORIZED"] },
];

export const CATEGORIES = CATEGORY_GROUPS.flatMap((group) => group.options);
