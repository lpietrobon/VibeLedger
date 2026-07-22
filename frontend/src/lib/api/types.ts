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

export type TransferCandidate = {
  id: number;
  detected_by: string;
  confirmed: boolean;
  amount: Money | null;
  out: {
    transaction_id: number;
    account_id?: number | null;
    date?: string | null;
    name?: string | null;
  };
  in: {
    transaction_id: number;
    account_id?: number | null;
    date?: string | null;
    name?: string | null;
  };
};

export type TransfersResponse = {
  total: number;
  items: TransferCandidate[];
};
