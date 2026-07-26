export type Money = number;

export type OverviewSummary = {
  asOfDate: string;
  netWorth: Money;
  assets: Money;
  liabilities: Money;
  monthSpend: Money;
  previousMonthSpend: Money;
  monthIncome: Money;
  previousMonthIncome: Money;
  netCashflow: Money;
  previousNetCashflow: Money;
  needsAttention: {
    unreviewedTransactions: number;
    uncategorizedTransactions: number;
    likelyRefunds: number;
    transferPairsPending: number;
  };
};

export type CashflowPoint = {
  month: string;
  income: Money;
  expenses: Money;
  net: Money;
};

export type CategoryComparisonPoint = {
  category: string;
  current: Money;
  previous: Money;
};

export type CategorySpendPoint = {
  category: string;
  spend: Money;
  color?: string;
};

export type Account = {
  id: number;
  name: string;
  display_name?: string;
  nickname?: string | null;
  mask?: string | null;
  subtype?: string | null;
  current_balance: Money;
  available_balance?: Money | null;
  currency?: string | null;
  credit_limit?: Money | null;
};

export type AccountSummary = {
  assets: Money;
  liabilities: Money;
  net_worth: Money;
  groups: Record<string, Account[]>;
};

export type Transaction = {
  id: number;
  plaid_transaction_id?: string;
  date: string;
  amount: Money;
  name: string;
  merchant_name?: string | null;
  effective_merchant?: string | null;
  effective_account_name?: string | null;
  pending: boolean;
  plaid_category_primary?: string | null;
  plaid_category_detailed?: string | null;
  plaid_category_friendly?: string | null;
  effective_category: string;
  category_source: "manual" | "rule" | "plaid" | "default";
  rule_id?: number | null;
  /** True when this transaction is one leg of a transfer pair (so it is
   *  excluded from spend/income analytics). */
  is_transfer?: boolean;
  transfer_pair_id?: number | null;
  refund_status?: "confirmed" | "likely" | "not_refund" | null;
  refund_match_transaction_id?: number | null;
  refund_reason?: string | null;
  annotation: {
    user_category?: string | null;
    merchant_name_override?: string | null;
    notes?: string | null;
    reviewed: boolean;
  };
};

export type TransactionsResponse = {
  total: number;
  items: Transaction[];
};

export type SpendingSummary = {
  periodLabel: string;
  total: Money;
  previousTotal: Money;
  change: Money;
  changePct: number | null;
  projection: Money;
  topDriver: {
    category: string;
    amount: Money;
  } | null;
};

export type CumulativeSpendingPoint = {
  day: number;
  current: Money | null;
  previous1: Money | null;
  previous2: Money | null;
  previous3: Money | null;
};

export type CategoryRule = {
  id: number;
  rank: number;
  enabled: boolean;
  description_regex?: string | null;
  account_name_regex?: string | null;
  min_amount?: Money | null;
  max_amount?: Money | null;
  assigned_category: string;
  name?: string | null;
  created_at: string;
  updated_at: string;
};

export type TransferLeg = {
  transaction_id: number;
  account_id?: number | null;
  /** Display name of the account this leg sits on — the point of a transfer. */
  account_name?: string | null;
  account_type?: string | null;
  date?: string | null;
  name?: string | null;
  amount?: Money | null;
};

export type TransferCandidate = {
  id: number;
  detected_by: string;
  confirmed: boolean;
  amount: Money | null;
  gap_days?: number | null;
  out: TransferLeg;
  in: TransferLeg;
};

export type TransfersResponse = {
  total: number;
  items: TransferCandidate[];
};

export type RecurringSeries = {
  merchant_key: string;
  merchant_label: string;
  /** Search query that matches the whole series — use for drilldowns, not merchant_label. */
  search_query: string;
  cadence: "weekly" | "biweekly" | "monthly" | "quarterly" | "yearly";
  occurrences: number;
  average_amount: Money;
  min_amount: Money;
  max_amount: Money;
  amount_consistent: boolean;
  first_date: string;
  last_date: string;
  next_expected_date: string;
  median_interval_days: number;
  monthly_estimate: Money;
  annual_estimate: Money;
  status: "active" | "inactive";
  auto_status: "active" | "inactive";
  manual_status: "kept" | "canceled" | null;
  category: string | null;
  account_ids: number[];
  sample_transaction_ids: number[];
};

export type RecurringResponse = {
  items: RecurringSeries[];
  summary: {
    count: number;
    active_count: number;
    active_monthly_estimate: Money;
    active_annual_estimate: Money;
  };
};

export type ConnectSession = {
  session_token: string;
  expires_at: string;
  connect_url: string;
};

export type ConnectStatus = {
  status: string;
  created_at: string;
  expires_at: string;
  completed_at: string | null;
  item_id: string | null;
};

export type CategoryEntry = {
  value: string;
  /** Transactions currently resolving to this category; 0 for rule/default entries. */
  count: number;
  source: "ledger" | "rule" | "default";
};

export type SearchSuggestion = {
  value: string;
  label: string;
  hint: string;
  has_values: boolean;
};

export type SearchSuggestionsResponse = {
  context: "field" | "value";
  field: string | null;
  replace_token: string;
  suggestions: SearchSuggestion[];
};

export type CategoryRuleDraft = {
  rank?: number;
  enabled?: boolean;
  description_regex?: string | null;
  account_name_regex?: string | null;
  min_amount?: Money | null;
  max_amount?: Money | null;
  assigned_category: string;
  name?: string | null;
};
