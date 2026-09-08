// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Transaction } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
  CATEGORIES: ["SHOPPING/GENERAL"],
  CATEGORY_GROUPS: [{ label: "Shopping", options: ["SHOPPING/GENERAL"] }],
  getTransactions: vi.fn(),
  syncAllAccounts: vi.fn(),
  patchTransactionAnnotation: vi.fn(),
  patchTransactionAnnotations: vi.fn(),
  getDuplicateCorrections: vi.fn(),
  createDuplicateCorrection: vi.fn(),
  reverseDuplicateCorrection: vi.fn(),
}));

vi.mock("@/lib/api/cache", () => ({
  invalidateLedger: vi.fn(async () => undefined),
}));

import * as api from "@/lib/api/client";
import { invalidateLedger } from "@/lib/api/cache";
import TransactionsPage from "./transactions";

const duplicateApi = api as typeof api & {
  getDuplicateCorrections: () => Promise<{ items: unknown[] }>;
  createDuplicateCorrection: (payload: {
    canonicalTransactionId: number;
    duplicateTransactionId: number;
  }) => Promise<unknown>;
  reverseDuplicateCorrection: (correctionId: number) => Promise<unknown>;
};

function transaction(id: number, name: string, duplicateStatus?: "canonical" | "duplicate"): Transaction {
  return {
    id,
    date: "2026-03-02",
    amount: 25,
    name,
    merchant_name: "Market",
    effective_merchant: "Market",
    effective_account_name: "Checking ··1234",
    pending: false,
    plaid_category_primary: "SHOPPING",
    plaid_category_detailed: "SHOPPING_GENERAL",
    plaid_category_friendly: "Shopping",
    effective_category: "SHOPPING/GENERAL",
    category_source: "plaid",
    is_transfer: false,
    is_transfer_candidate: false,
    refund_status: null,
    duplicate_status: duplicateStatus,
    annotation: { reviewed: true },
  };
}

const marketA = transaction(101, "MARKET A");
const marketB = transaction(102, "MARKET B");
const activeCorrection = {
  id: 9001,
  canonical_transaction_id: 101,
  duplicate_transaction_id: 102,
  status: "active" as const,
};

let host: HTMLDivElement;
let root: Root;

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

function mount() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  root = createRoot(host);
  act(() => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <TransactionsPage />
      </QueryClientProvider>,
    );
  });
}

function button(label: string) {
  return [...host.querySelectorAll<HTMLButtonElement>("button")].find(
    (candidate) => candidate.textContent?.trim() === label,
  );
}

function rowCheckboxes(container: Element) {
  return [...container.querySelectorAll<HTMLInputElement>('input[type="checkbox"][aria-label]')].filter(
    (input) => input.getAttribute("aria-label") !== "Select all shown",
  );
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement("div");
  document.body.appendChild(host);
  window.history.replaceState({}, "", "/vibeledger/frontend/transactions");
  vi.mocked(api.getTransactions).mockResolvedValue({ total: 2, items: [marketA, marketB] });
  vi.mocked(duplicateApi.getDuplicateCorrections).mockResolvedValue({ items: [] });
  vi.mocked(duplicateApi.createDuplicateCorrection).mockResolvedValue(activeCorrection);
  vi.mocked(duplicateApi.reverseDuplicateCorrection).mockResolvedValue({ id: 9001, status: "reversed" });
});

afterEach(() => {
  act(() => root?.unmount());
  host.remove();
  vi.clearAllMocks();
});

describe("PI-18 duplicate-correction UI adversarial verification", () => {
  it("keeps the correction dialog open and reports a create failure without invalidating", async () => {
    vi.mocked(duplicateApi.createDuplicateCorrection).mockRejectedValue(new Error("server rejected correction"));
    mount();
    await settle();
    await settle();

    const desktop = host.querySelector('div[class~="hidden"][class~="md:block"]');
    const selectedRows = rowCheckboxes(desktop!);
    await act(async () => {
      selectedRows[0].click();
      selectedRows[1].click();
    });
    await act(async () => button("Mark as duplicates")!.click());
    await settle();
    await act(async () => button("Confirm duplicate correction")!.click());
    await settle();

    expect(host.querySelector('[role="dialog"][aria-label="Duplicate correction"]')).not.toBeNull();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("server rejected correction");
    expect(invalidateLedger).not.toHaveBeenCalled();
  });

  it("keeps reversal confirmation open and reports a reverse failure without invalidating", async () => {
    vi.mocked(api.getTransactions).mockResolvedValue({
      total: 2,
      items: [transaction(101, "MARKET A", "canonical"), transaction(102, "MARKET B", "duplicate")],
    });
    vi.mocked(duplicateApi.getDuplicateCorrections).mockResolvedValue({ items: [activeCorrection] });
    vi.mocked(duplicateApi.reverseDuplicateCorrection).mockRejectedValue(new Error("server rejected reversal"));
    mount();
    await settle();
    await settle();

    const mobile = host.querySelector('div[class~="md:hidden"]');
    await act(async () => mobile?.querySelector("button")?.click());
    await act(async () => button("Reverse duplicate correction")!.click());
    await act(async () => button("Reverse correction")!.click());
    await settle();

    expect(host.querySelector('[role="dialog"][aria-label="Reverse duplicate correction"]')).not.toBeNull();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("server rejected reversal");
    expect(invalidateLedger).not.toHaveBeenCalled();
  });
});
