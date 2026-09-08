// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Transaction } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
  CATEGORIES: ["FOOD/OTHER", "SHOPPING/GENERAL"],
  CATEGORY_GROUPS: [
    { label: "Food", options: ["FOOD/OTHER"] },
    { label: "Shopping", options: ["SHOPPING/GENERAL"] },
  ],
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

type DuplicateUiApi = typeof api & {
  getDuplicateCorrections: () => Promise<{ items: unknown[] }>;
  createDuplicateCorrection: (payload: {
    canonicalTransactionId: number;
    duplicateTransactionId: number;
  }) => Promise<unknown>;
  reverseDuplicateCorrection: (correctionId: number) => Promise<unknown>;
};

const duplicateApi = api as unknown as DuplicateUiApi;

type DuplicateStatus = "canonical" | "duplicate";
type FixtureTransaction = Transaction & {
  duplicate_status?: DuplicateStatus;
};

const fixture = {
  marketA: 101,
  marketB: 102,
  coffeeA: 103,
  coffeeB: 104,
};

function transaction(
  id: number,
  name: string,
  duplicateStatus?: DuplicateStatus,
): FixtureTransaction {
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

const beforeCorrection: FixtureTransaction[] = [
  transaction(fixture.marketA, "MARKET A"),
  transaction(fixture.marketB, "MARKET B"),
  transaction(fixture.coffeeA, "COFFEE A"),
  transaction(fixture.coffeeB, "COFFEE B"),
];

const afterCorrection: FixtureTransaction[] = [
  transaction(fixture.marketA, "MARKET A", "canonical"),
  transaction(fixture.marketB, "MARKET B", "duplicate"),
  transaction(fixture.coffeeA, "COFFEE A"),
  transaction(fixture.coffeeB, "COFFEE B"),
];

const activeCorrection = {
  id: 9001,
  canonical_transaction_id: fixture.marketA,
  duplicate_transaction_id: fixture.marketB,
  status: "active",
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

function pressKey(element: HTMLElement, key: string) {
  element.focus();
  element.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
  element.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
}

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  host = document.createElement("div");
  document.body.appendChild(host);
  window.history.replaceState({}, "", "/vibeledger/frontend/transactions");

  vi.mocked(api.getTransactions).mockResolvedValue({
    total: beforeCorrection.length,
    items: beforeCorrection,
  });
  vi.mocked(duplicateApi.getDuplicateCorrections).mockResolvedValue({ items: [] });
  vi.mocked(duplicateApi.createDuplicateCorrection).mockResolvedValue(activeCorrection);
  vi.mocked(duplicateApi.reverseDuplicateCorrection).mockResolvedValue({ id: 9001, status: "reversed" });
});

afterEach(() => {
  act(() => root?.unmount());
  host.remove();
  vi.clearAllMocks();
});

describe("PI-17 frozen duplicate-correction interaction contract", () => {
  it("supports desktop exact-two selection, keyboard confirmation, canonical choice, POST, and refresh", async () => {
    mount();
    await settle();
    await settle();

    const desktop = host.querySelector('div[class~="hidden"][class~="md:block"]');
    expect(desktop).not.toBeNull();
    const selectedRows = rowCheckboxes(desktop!);
    expect(selectedRows).toHaveLength(4);
    await act(async () => {
      selectedRows[0].click();
      selectedRows[1].click();
    });

    expect(host.textContent).toContain("2 selected");
    const mark = button("Mark as duplicates");
    expect(mark, "PI-05 must expose the duplicate action for exactly two rows").toBeDefined();
    pressKey(mark!, "Enter");
    await settle();

    expect(host.textContent).toContain("Choose the canonical transaction");
    expect(host.textContent).toContain(
      "Both imported records will remain visible. Only the record marked duplicate will be excluded from spending and income totals.",
    );
    const canonicalChoices = [...host.querySelectorAll<HTMLInputElement>('input[type="radio"]')];
    expect(canonicalChoices).toHaveLength(2);
    await act(async () => canonicalChoices[1].click());
    expect(canonicalChoices[1].checked).toBe(true);

    const confirm = button("Confirm duplicate correction");
    expect(confirm).toBeDefined();
    await act(async () => confirm!.click());
    await settle();

    expect(duplicateApi.createDuplicateCorrection).toHaveBeenCalledWith({
      canonicalTransactionId: fixture.marketB,
      duplicateTransactionId: fixture.marketA,
    });
    expect(invalidateLedger).toHaveBeenCalled();
  });

  it("supports mobile selection and keyboard activation of the exact-two action", async () => {
    mount();
    await settle();
    await settle();

    const mobile = host.querySelector('div[class~="md:hidden"]');
    expect(mobile).not.toBeNull();
    const selectedRows = rowCheckboxes(mobile!);
    expect(selectedRows).toHaveLength(4);
    await act(async () => {
      selectedRows[0].click();
      selectedRows[1].click();
    });
    const mark = button("Mark as duplicates");
    expect(mark).toBeDefined();
    pressKey(mark!, "Enter");
    await settle();
    expect(host.querySelector('[role="dialog"][aria-label="Duplicate correction"]')).not.toBeNull();
  });

  it("gives deterministic feedback for one or more than two selected rows", async () => {
    mount();
    await settle();
    await settle();

    const desktop = host.querySelector('div[class~="hidden"][class~="md:block"]');
    const selectedRows = rowCheckboxes(desktop!);
    await act(async () => selectedRows[0].click());
    const oneSelected = button("Mark as duplicates");
    expect(oneSelected).toBeDefined();
    expect(oneSelected!.disabled).toBe(true);
    expect(host.textContent).toContain("Select exactly two transactions to mark as duplicates.");

    await act(async () => {
      selectedRows[1].click();
      selectedRows[2].click();
    });
    expect(host.textContent).toContain("Select exactly two transactions to mark as duplicates.");
    expect(button("Mark as duplicates")!.disabled).toBe(true);
  });

  it("renders relationship labels, reversal confirmation, DELETE payload, and refresh", async () => {
    vi.mocked(api.getTransactions).mockResolvedValue({
      total: afterCorrection.length,
      items: afterCorrection,
    });
    vi.mocked(duplicateApi.getDuplicateCorrections).mockResolvedValue({ items: [activeCorrection] });
    mount();
    await settle();
    await settle();

    expect(host.textContent).toContain("Canonical");
    expect(host.textContent).toContain("Marked duplicate");

    const mobile = host.querySelector('div[class~="md:hidden"]');
    const firstRow = mobile?.querySelector("button");
    expect(firstRow).not.toBeNull();
    await act(async () => firstRow!.click());
    expect(host.textContent).toContain("Reverse duplicate correction");
    const reverse = button("Reverse duplicate correction");
    expect(reverse).toBeDefined();
    pressKey(reverse!, "Enter");
    await settle();
    expect(host.textContent).toContain("Both records will again count normally.");

    const confirm = button("Reverse correction");
    expect(confirm).toBeDefined();
    await act(async () => confirm!.click());
    await settle();
    expect(duplicateApi.reverseDuplicateCorrection).toHaveBeenCalledWith(activeCorrection.id);
    expect(invalidateLedger).toHaveBeenCalled();
  });

  it("does not infer duplicate state for two similar-looking legitimate charges", async () => {
    mount();
    await settle();

    expect(host.textContent).not.toContain("Canonical");
    expect(host.textContent).not.toContain("Marked duplicate");
    expect(duplicateApi.createDuplicateCorrection).not.toHaveBeenCalled();
  });
});
