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
  SearchSuggestionsResponse,
  CategoryEntry,
  CashflowSankey,
  CategoryMovers,
  DailySpend,
  ComparisonReporting,
  ReportingScope,
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
  reporting?: ReportingResponse;
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

type ReportingScopeResponse = {
  currency: string | null;
  currency_status: "empty" | "unknown" | "mixed" | "single";
  currencies: string[];
  history_coverage: "unverified";
  duplicate_account_coverage: "unverified";
  qualification: string;
  start_date: string | null;
  end_date: string | null;
  recorded_row_count: number;
  first_recorded_date: string | null;
  last_recorded_date: string | null;
};

type ReportingResponse = ReportingScopeResponse & {
  reporting_date: string;
  current_period: ReportingScopeResponse;
  previous_period: ReportingScopeResponse;
  comparison_available: boolean;
  comparison_qualification: string;
  projection_qualification?: string;
};

const REPORTING_UNAVAILABLE =
  "Reporting metadata is unavailable. Totals show recorded activity, but period coverage and comparison confidence cannot be verified until the API is updated.";

function mapReportingScope(r?: Partial<ReportingScopeResponse>): ReportingScope {
  const status = r?.currency_status;
  return {
    currency: r?.currency ?? null,
    currencyStatus: status === "empty" || status === "single" || status === "mixed" || status === "unknown"
      ? status
      : "unknown",
    currencies: Array.isArray(r?.currencies) ? r.currencies : [],
    historyCoverage: "unverified",
    duplicateAccountCoverage: "unverified",
    qualification: r?.qualification ?? REPORTING_UNAVAILABLE,
    startDate: r?.start_date ?? null,
    endDate: r?.end_date ?? null,
    recordedRowCount: typeof r?.recorded_row_count === "number" ? r.recorded_row_count : 0,
    firstRecordedDate: r?.first_recorded_date ?? null,
    lastRecordedDate: r?.last_recorded_date ?? null,
  };
}

function mapReporting(r?: Partial<ReportingResponse>): ComparisonReporting {
  const hasComparablePeriods = Boolean(r?.current_period && r?.previous_period);
  return {
    ...mapReportingScope(r),
    reportingDate: r?.reporting_date ?? "",
    currentPeriod: mapReportingScope(r?.current_period ?? r),
    previousPeriod: mapReportingScope(r?.previous_period),
    comparisonAvailable: hasComparablePeriods && r?.comparison_available === true,
    comparisonQualification: hasComparablePeriods
      ? (r?.comparison_qualification ?? REPORTING_UNAVAILABLE)
      : REPORTING_UNAVAILABLE,
    projectionQualification: r?.projection_qualification,
  };
}

export async function getOverviewSummary(): Promise<OverviewSummary> {
  const r = await jsonFetch<OverviewResponse>("/analytics/overview");
  return {
    asOfDate: r.as_of_date,
    reporting: mapReporting(r.reporting),
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
  reporting?: ReportingResponse;
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
    reporting: mapReporting(r.reporting),
    periodLabel: r.period_label,
    total: r.total,
    previousTotal: r.previous_total,
    change: r.change,
    changePct: r.change_pct,
    projection: r.projection,
    topDriver: r.top_driver,
  };
}

export async function getCategoryComparison(
  granularity: "monthly" | "yearly" = "monthly",
): Promise<CategoryComparisonPoint[]> {
  const r = await fetchSpendingSummary(granularity);
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

type SankeyResponse = {
  sankey_supported: boolean;
  visualization_qualification: string | null;
  negative_categories: { category: string; amount: number }[];
  income: number;
  total_spend: number;
  savings: number;
  deficit: number;
  income_sources: { category: string; amount: number }[];
  buckets: { bucket: string; amount: number; categories: { category: string; amount: number }[] }[];
};

export async function getCashflowSankey(params?: {
  startDate?: string;
  endDate?: string;
}): Promise<CashflowSankey> {
  const r = await jsonFetch<SankeyResponse>("/analytics/cashflow-sankey", {
    start_date: params?.startDate,
    end_date: params?.endDate,
  });
  return {
    sankeySupported: r.sankey_supported,
    visualizationQualification: r.visualization_qualification,
    negativeCategories: r.negative_categories,
    income: r.income,
    totalSpend: r.total_spend,
    savings: r.savings,
    deficit: r.deficit,
    incomeSources: r.income_sources,
    buckets: r.buckets,
  };
}

export async function getCategoryMovers(params?: {
  month?: string;
  limit?: number;
}): Promise<CategoryMovers> {
  const r = await jsonFetch<{
    month: string;
    previous_month: string;
    items: { category: string; current: number; previous: number; change: number }[];
  }>("/analytics/category-movers", { month: params?.month, limit: params?.limit });
  return { month: r.month, previousMonth: r.previous_month, items: r.items };
}

export async function getDailySpend(params?: { year?: number }): Promise<DailySpend> {
  const r = await jsonFetch<{
    year: number;
    available_years: number[];
    days: { date: string; amount: number }[];
  }>("/analytics/daily-spend", { year: params?.year });
  return { year: r.year, availableYears: r.available_years, days: r.days };
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

/** Every category in use, plus rule targets and curated defaults. */
export async function getCategoryCatalog(): Promise<CategoryEntry[]> {
  const body = await jsonFetch<{ items: CategoryEntry[] }>("/categories");
  return body.items;
}

export async function getSearchSuggestions(q: string): Promise<SearchSuggestionsResponse> {
  return jsonFetch<SearchSuggestionsResponse>("/transactions/search-suggestions", { q: q || undefined });
}

/** Replace the trailing in-progress token with an accepted suggestion. */
export function applySuggestion(query: string, replaceToken: string, value: string): string {
  const base = replaceToken ? query.slice(0, query.length - replaceToken.length) : query;
  const needsSpace = base && !base.endsWith(" ");
  const joined = `${base}${needsSpace ? " " : ""}${value}`;
  // Field tokens end with ":" and still need a value typed; others complete a term.
  return joined.endsWith(":") ? joined : `${joined} `;
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
  const r = await jsonFetch<RecurringResponse & { reporting?: ReportingScopeResponse }>("/analytics/recurring", {
    status: params?.status,
    min_monthly: params?.minMonthly,
  });
  return { ...r, reporting: r.reporting ? mapReportingScope(r.reporting) : undefined };
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
