// Category → chart color. A small presentation constant (not data), shared by
// the Overview and category charts.
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

// Top-level category bucket (the part of effective_category before the first
// "/") -> chart color, for the cashflow Sankey. Fixed order, not cycled.
export const BUCKET_COLORS: Record<string, string> = {
  HOUSING: "#3b82f6",
  FOOD: "#ef4444",
  TRANSPORT: "#f59e0b",
  SHOPPING: "#a855f7",
  FUN: "#ec4899",
  HEALTH: "#10b981",
  FINANCE: "#6366f1",
  SERVICES: "#14b8a6",
  SUBSCRIPTIONS: "#f97316",
  UNCATEGORIZED: "#94a3b8",
};

export const BUCKET_COLOR_FALLBACK = "#64748b";
