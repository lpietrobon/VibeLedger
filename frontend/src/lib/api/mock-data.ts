import type {
  OverviewSummary,
  CashflowPoint,
  CategoryComparisonPoint,
  CategorySpendPoint,
  AccountSummary,
  Transaction,
  SpendingSummary,
  CumulativeSpendingPoint,
} from "./types";

export const CATEGORY_COLORS: Record<string, string> = {
  Housing: "#3b82f6",
  Food: "#ef4444",
  Transportation: "#f59e0b",
  Shopping: "#a855f7",
  Travel: "#14b8a6",
  Entertainment: "#ec4899",
  Health: "#10b981",
  Utilities: "#6366f1",
  Subscriptions: "#f97316",
  Uncategorized: "#94a3b8",
};

export const overviewSummary: OverviewSummary = {
  asOfDate: "2026-07-18",
  netWorth: 184320.42,
  assets: 232480.11,
  liabilities: 48159.69,
  monthSpend: 4820.16,
  previousMonthSpend: 5411.02,
  monthIncome: 8420.0,
  previousMonthIncome: 8420.0,
  netCashflow: 3599.84,
  previousNetCashflow: 3008.98,
  needsAttention: {
    unreviewedTransactions: 7,
    uncategorizedTransactions: 3,
    likelyRefunds: 1,
    transferPairsPending: 2,
  },
};

export const cashflowTrend: CashflowPoint[] = [
  { month: "2025-08", income: 8420, expenses: 5210, net: 3210 },
  { month: "2025-09", income: 8420, expenses: 4980, net: 3440 },
  { month: "2025-10", income: 8720, expenses: 5540, net: 3180 },
  { month: "2025-11", income: 8420, expenses: 6120, net: 2300 },
  { month: "2025-12", income: 9200, expenses: 7480, net: 1720 },
  { month: "2026-01", income: 8420, expenses: 4980, net: 3440 },
  { month: "2026-02", income: 8420, expenses: 5120, net: 3300 },
  { month: "2026-03", income: 8420, expenses: 5620, net: 2800 },
  { month: "2026-04", income: 8620, expenses: 5010, net: 3610 },
  { month: "2026-05", income: 8420, expenses: 4890, net: 3530 },
  { month: "2026-06", income: 8420, expenses: 5411, net: 3009 },
  { month: "2026-07", income: 8420, expenses: 4820, net: 3600 },
];

export const categoryComparison: CategoryComparisonPoint[] = [
  { category: "Housing", current: 1850, previous: 1850 },
  { category: "Food", current: 682, previous: 812 },
  { category: "Transportation", current: 312, previous: 428 },
  { category: "Shopping", current: 421, previous: 612 },
  { category: "Travel", current: 0, previous: 340 },
  { category: "Entertainment", current: 168, previous: 210 },
  { category: "Health", current: 84, previous: 145 },
  { category: "Utilities", current: 246, previous: 231 },
  { category: "Subscriptions", current: 128, previous: 128 },
  { category: "Uncategorized", current: 92, previous: 55 },
];

export const categorySpend: CategorySpendPoint[] = categoryComparison
  .filter((c) => c.current > 0)
  .map((c) => ({ category: c.category, spend: c.current, color: CATEGORY_COLORS[c.category] }));

export const accountsSummary: AccountSummary = {
  assets: 232480.11,
  liabilities: 48159.69,
  net_worth: 184320.42,
  groups: {
    Cash: [
      { id: 1, name: "Everyday Checking", mask: "4821", subtype: "checking", current_balance: 6210.44, available_balance: 6210.44, currency: "USD" },
      { id: 2, name: "High-Yield Savings", mask: "0912", subtype: "savings", current_balance: 24800.11, available_balance: 24800.11, currency: "USD" },
    ],
    Investments: [
      { id: 3, name: "Brokerage", mask: "7781", subtype: "brokerage", current_balance: 82340.56, currency: "USD" },
      { id: 4, name: "401(k)", mask: null, subtype: "401k", current_balance: 104129.0, currency: "USD" },
    ],
    Credit: [
      { id: 5, name: "Sapphire Card", mask: "5541", subtype: "credit card", current_balance: -1240.18, credit_limit: 15000, currency: "USD" },
      { id: 6, name: "Amex Gold", mask: "3311", subtype: "credit card", current_balance: -841.51, credit_limit: 20000, currency: "USD" },
    ],
    Loans: [
      { id: 7, name: "Auto Loan", mask: "0021", subtype: "auto", current_balance: -12078.0, currency: "USD" },
      { id: 8, name: "Mortgage", mask: "9910", subtype: "mortgage", current_balance: -34000.0, currency: "USD" },
    ],
  },
};

const t = (
  id: number,
  date: string,
  amount: number,
  name: string,
  merchant: string,
  category: string,
  account: string,
  extra: Partial<Transaction> = {},
): Transaction => ({
  id,
  date,
  amount,
  name,
  merchant_name: merchant,
  effective_merchant: merchant,
  effective_account_name: account,
  pending: false,
  effective_category: category,
  category_source: "plaid",
  annotation: { reviewed: true },
  ...extra,
});

export const transactions: Transaction[] = [
  t(101, "2026-07-17", 42.18, "WHOLE FOODS #451", "Whole Foods", "Food", "Sapphire Card"),
  t(102, "2026-07-17", 12.4, "BLUE BOTTLE", "Blue Bottle Coffee", "Food", "Amex Gold"),
  t(103, "2026-07-16", 89.99, "AMAZON.COM", "Amazon", "Shopping", "Sapphire Card", { annotation: { reviewed: false } }),
  t(104, "2026-07-16", 1850.0, "RENT JULY", "Landlord LLC", "Housing", "Everyday Checking"),
  t(105, "2026-07-15", 24.5, "UBER TRIP", "Uber", "Transportation", "Amex Gold"),
  t(106, "2026-07-15", -1240.0, "PAYROLL DEPOSIT", "Acme Corp", "Income", "Everyday Checking"),
  t(107, "2026-07-14", 15.99, "NETFLIX", "Netflix", "Subscriptions", "Sapphire Card"),
  t(108, "2026-07-14", 68.22, "SHELL OIL", "Shell", "Transportation", "Sapphire Card"),
  t(109, "2026-07-13", 132.4, "TARGET", "Target", "Shopping", "Amex Gold", { annotation: { reviewed: false } }),
  t(110, "2026-07-13", -48.0, "AMAZON REFUND", "Amazon", "Shopping", "Sapphire Card", {
    refund_status: "likely",
    refund_reason: "Matches recent Amazon purchase within 14 days",
    annotation: { reviewed: false },
  }),
  t(111, "2026-07-12", 210.55, "DELTA AIR LINES", "Delta", "Travel", "Sapphire Card"),
  t(112, "2026-07-11", 32.1, "CHIPOTLE", "Chipotle", "Food", "Amex Gold"),
  t(113, "2026-07-11", 9.99, "SPOTIFY", "Spotify", "Subscriptions", "Sapphire Card"),
  t(114, "2026-07-10", 24.0, "MOVIE THEATER", "AMC Theatres", "Entertainment", "Amex Gold"),
  t(115, "2026-07-10", 145.0, "COSTCO", "Costco", "Food", "Sapphire Card"),
  t(116, "2026-07-09", 62.4, "PG&E", "PG&E", "Utilities", "Everyday Checking"),
  t(117, "2026-07-09", 89.0, "COMCAST", "Comcast", "Utilities", "Everyday Checking"),
  t(118, "2026-07-08", 18.75, "STARBUCKS", "Starbucks", "Food", "Amex Gold"),
  t(119, "2026-07-08", 41.2, "CVS PHARMACY", "CVS", "Health", "Sapphire Card"),
  t(120, "2026-07-07", 55.0, "LYFT", "Lyft", "Transportation", "Amex Gold"),
  t(121, "2026-07-07", 24.99, "ICLOUD STORAGE", "Apple", "Subscriptions", "Sapphire Card"),
  t(122, "2026-07-06", 340.0, "APPLE STORE", "Apple", "Shopping", "Sapphire Card"),
  t(123, "2026-07-06", 78.4, "TRADER JOE'S", "Trader Joe's", "Food", "Amex Gold"),
  t(124, "2026-07-05", 12.0, "PARKING METER", "SF Parking", "Transportation", "Sapphire Card", {
    effective_category: "Uncategorized",
    category_source: "default",
    annotation: { reviewed: false },
  }),
  t(125, "2026-07-05", 22.5, "LOCAL CAFE", "Café Reveille", "Food", "Amex Gold"),
  t(126, "2026-07-04", 88.0, "RESTAURANT", "Nopa", "Food", "Sapphire Card", {
    effective_category: "Uncategorized",
    category_source: "default",
    annotation: { reviewed: false },
  }),
  t(127, "2026-07-03", 18.0, "VENMO", "Venmo", "Uncategorized", "Everyday Checking", {
    effective_category: "Uncategorized",
    category_source: "default",
    annotation: { reviewed: false },
  }),
  t(128, "2026-07-02", 145.0, "PELOTON", "Peloton", "Subscriptions", "Sapphire Card"),
  t(129, "2026-07-02", 14.5, "COFFEE", "Sightglass", "Food", "Amex Gold"),
  t(130, "2026-07-01", 24.99, "GYM MEMBERSHIP", "Equinox", "Health", "Sapphire Card"),
  t(131, "2026-07-18", 32.15, "PENDING GROCERY", "Safeway", "Food", "Sapphire Card", { pending: true, annotation: { reviewed: false } }),
];

export const spendingSummaryMonthly: SpendingSummary = {
  periodLabel: "July 2026",
  total: 4820.16,
  previousTotal: 5411.02,
  change: -590.86,
  changePct: -10.92,
  projection: 5210.0,
  topDriver: { category: "Shopping", amount: -191 },
};

export const spendingSummaryYearly: SpendingSummary = {
  periodLabel: "2026 YTD",
  total: 37210.44,
  previousTotal: 41120.19,
  change: -3909.75,
  changePct: -9.5,
  projection: 63800.0,
  topDriver: { category: "Travel", amount: -1240 },
};

export const cumulativeSpending: CumulativeSpendingPoint[] = Array.from({ length: 31 }, (_, i) => {
  const day = i + 1;
  const cur = day <= 18 && [1, 2, 4, 7, 9, 11, 14, 16, 18].includes(day) ? day * 268 : null;
  return {
    day,
    current: cur,
    previous1: day % 3 === 0 ? null : Math.round(day * 175 + day * day * 1.2),
    previous2: day % 4 === 0 ? null : Math.round(day * 162 + day * day * 1.0),
    previous3: day % 5 === 0 ? null : Math.round(day * 158 + day * day * 0.9),
  };
});

export const cumulativeSpendingYearly: CumulativeSpendingPoint[] = Array.from({ length: 12 }, (_, i) => {
  const day = i + 1;
  return {
    day,
    current: day <= 7 ? day * 5100 : null,
    previous1: day * 4820,
    previous2: day * 4610,
    previous3: day * 4390,
  };
});
