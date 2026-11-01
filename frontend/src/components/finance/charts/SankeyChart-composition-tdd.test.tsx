// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import SankeyChart from "./SankeyChart";
import type { CashflowSankey } from "@/lib/api/types";

type CompositionFixture = {
  name: string;
  data: CashflowSankey;
  expectedKeys: string[];
  forbiddenKeys: string[];
  expectedLinks: string[];
};

const normalSurplus = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 900,
  income: 3000,
  totalSpend: -900,
  savings: 2100,
  deficit: 0,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [{ bucket: "FOOD", amount: 900, categories: [{ category: "Groceries", amount: 900 }] }],
  incomeSources: [{ category: "Salary", amount: 3000 }],
} satisfies CashflowSankey;

const exactBalance = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 900,
  income: 900,
  totalSpend: -900,
  savings: 0,
  deficit: 0,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [{ bucket: "FOOD", amount: 900, categories: [{ category: "Groceries", amount: 900 }] }],
  incomeSources: [{ category: "Salary", amount: 900 }],
} satisfies CashflowSankey;

const deficit = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 1200,
  income: 900,
  totalSpend: -1200,
  savings: 0,
  deficit: 300,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [{ bucket: "FOOD", amount: 1200, categories: [{ category: "Groceries", amount: 1200 }] }],
  incomeSources: [],
} satisfies CashflowSankey;

const refundCredit = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [{ category: "SHOPPING", amount: -120 }],
  positiveNetSpend: 90,
  income: 3000,
  totalSpend: -30,
  savings: 3030,
  deficit: 0,
  netRefundCredits: 120,
  netRefundCreditCategories: [{ category: "SHOPPING", amount: 120 }],
  buckets: [{ bucket: "FOOD", amount: 90, categories: [{ category: "Groceries", amount: 90 }] }],
  incomeSources: [],
} satisfies CashflowSankey;

const refundOnly = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [{ category: "SHOPPING", amount: -120 }],
  positiveNetSpend: 0,
  income: 3000,
  totalSpend: -120,
  savings: 3120,
  deficit: 0,
  netRefundCredits: 120,
  netRefundCreditCategories: [{ category: "SHOPPING", amount: 120 }],
  buckets: [],
  incomeSources: [],
} satisfies CashflowSankey;

const refundOnlyZeroIncome = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [{ category: "SHOPPING", amount: -120 }],
  positiveNetSpend: 0,
  income: 0,
  totalSpend: -120,
  savings: 120,
  deficit: 0,
  netRefundCredits: 120,
  netRefundCreditCategories: [{ category: "SHOPPING", amount: 120 }],
  buckets: [],
  incomeSources: [],
} satisfies CashflowSankey;

const zeroIncomeSpending = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 100,
  income: 0,
  totalSpend: -100,
  savings: 0,
  deficit: 100,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [{ bucket: "FOOD", amount: 100, categories: [{ category: "Groceries", amount: 100 }] }],
  incomeSources: [],
} satisfies CashflowSankey;

const zeroSpending = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 0,
  income: 1000,
  totalSpend: 0,
  savings: 1000,
  deficit: 0,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [],
  incomeSources: [],
} satisfies CashflowSankey;

const emptyPeriod = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 0,
  income: 0,
  totalSpend: 0,
  savings: 0,
  deficit: 0,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [],
  incomeSources: [],
} satisfies CashflowSankey;

const netZeroCategory = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [],
  positiveNetSpend: 0,
  income: 1000,
  totalSpend: 0,
  savings: 1000,
  deficit: 0,
  netRefundCredits: 0,
  netRefundCreditCategories: [],
  buckets: [{ bucket: "FOOD", amount: 0, categories: [{ category: "NET_ZERO", amount: 0 }] }],
  incomeSources: [],
} satisfies CashflowSankey;

const fixtures: CompositionFixture[] = [
  {
    name: "normal surplus",
    data: normalSurplus,
    expectedKeys: ["__income_node__", "bucket:FOOD", "__savings__"],
    forbiddenKeys: ["__available__", "__deficit__", "__refund_credits__"],
    expectedLinks: ["Income → FOOD: $900.00", "Income → Savings: $2,100.00"],
  },
  {
    name: "exact balance",
    data: exactBalance,
    expectedKeys: ["__income_node__", "bucket:FOOD"],
    forbiddenKeys: ["__available__", "__savings__", "__deficit__", "__refund_credits__"],
    expectedLinks: ["Income → FOOD: $900.00"],
  },
  {
    name: "deficit",
    data: deficit,
    expectedKeys: ["__income_node__", "__available__", "__deficit__", "bucket:FOOD"],
    forbiddenKeys: ["__savings__", "__refund_credits__"],
    expectedLinks: [
      "Deficit funding → Available cash: $300.00",
      "Income → Available cash: $900.00",
      "Available cash → FOOD: $1,200.00",
    ],
  },
  {
    name: "refund credit",
    data: refundCredit,
    expectedKeys: ["__income_node__", "__available__", "__refund_credits__", "bucket:FOOD", "__savings__"],
    forbiddenKeys: ["__deficit__"],
    expectedLinks: [
      "Net refund credits → Available cash: $120.00",
      "Income → Available cash: $3,000.00",
      "Available cash → FOOD: $90.00",
      "Available cash → Savings: $3,030.00",
    ],
  },
  {
    name: "refund-only with income",
    data: refundOnly,
    expectedKeys: ["__income_node__", "__available__", "__refund_credits__", "__savings__"],
    forbiddenKeys: ["__deficit__"],
    expectedLinks: [
      "Net refund credits → Available cash: $120.00",
      "Income → Available cash: $3,000.00",
      "Available cash → Savings: $3,120.00",
    ],
  },
  {
    name: "refund-only with zero income",
    data: refundOnlyZeroIncome,
    expectedKeys: ["__available__", "__refund_credits__", "__savings__"],
    forbiddenKeys: ["__income_node__", "__deficit__"],
    expectedLinks: [
      "Net refund credits → Available cash: $120.00",
      "Available cash → Savings: $120.00",
    ],
  },
  {
    name: "zero income with spending",
    data: zeroIncomeSpending,
    expectedKeys: ["__available__", "__deficit__", "bucket:FOOD"],
    forbiddenKeys: ["__income_node__", "__savings__", "__refund_credits__"],
    expectedLinks: [
      "Deficit funding → Available cash: $100.00",
      "Available cash → FOOD: $100.00",
    ],
  },
  {
    name: "zero spending",
    data: zeroSpending,
    expectedKeys: ["__income_node__", "__savings__"],
    forbiddenKeys: ["__available__", "__deficit__", "__refund_credits__"],
    expectedLinks: ["Income → Savings: $1,000.00"],
  },
  {
    name: "net-zero category",
    data: netZeroCategory,
    expectedKeys: ["__income_node__", "__savings__"],
    forbiddenKeys: ["__available__", "bucket:FOOD", "cat:NET_ZERO"],
    expectedLinks: ["Income → Savings: $1,000.00"],
  },
];

function renderFixture(data: CashflowSankey, expanded: string | null = null) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(<SankeyChart data={data} expanded={expanded} onToggle={() => {}} />));
  return { host, root };
}

function renderedKeys(host: HTMLElement) {
  return [...host.querySelectorAll<SVGGElement>("[data-sankey-key]")].map((node) => node.dataset.sankeyKey);
}

function renderedLinkTitles(host: HTMLElement) {
  return [...host.querySelectorAll<SVGPathElement>("path")]
    .map((path) => path.querySelector("title")?.textContent)
    .filter((title): title is string => Boolean(title));
}

describe("PI-23 frozen Sankey composition contract", () => {
  const rendered: Array<{ host: HTMLDivElement; root: Root }> = [];

  afterEach(() => {
    for (const { root, host } of rendered.splice(0)) {
      act(() => root.unmount());
      host.remove();
    }
  });

  it.each(fixtures)("$name has the accepted visible composition and server amounts", (fixture) => {
    const result = renderFixture(fixture.data);
    rendered.push(result);

    const keys = renderedKeys(result.host);
    for (const key of fixture.expectedKeys) expect(keys).toContain(key);
    for (const key of fixture.forbiddenKeys) expect(keys).not.toContain(key);

    expect([...renderedLinkTitles(result.host)].sort()).toEqual([...fixture.expectedLinks].sort());
    expect(renderedLinkTitles(result.host).some((title) => title.includes("-$"))).toBe(false);
  });

  it("keeps the zero-income, zero-spending period truthful without a drawable graph", () => {
    const result = renderFixture(emptyPeriod);
    rendered.push(result);

    expect(result.host.querySelector("svg")).toBeNull();
    expect(result.host.textContent).toContain("No income or spending in this period.");
  });

  it("omits the adaptive hub in the ordinary expanded-category path", () => {
    const result = renderFixture(normalSurplus, "FOOD");
    rendered.push(result);

    expect(renderedKeys(result.host)).toEqual(
      expect.arrayContaining(["__income_node__", "bucket:FOOD", "cat:Groceries", "__savings__"]),
    );
    expect(renderedKeys(result.host)).not.toContain("__available__");
    expect(renderedLinkTitles(result.host)).toEqual(
      expect.arrayContaining(["Income → FOOD: $900.00", "FOOD → Groceries: $900.00", "Income → Savings: $2,100.00"]),
    );
  });

  it("retains stable income-source keys without changing ordinary flow amounts", () => {
    const result = renderFixture(normalSurplus, "__income__");
    rendered.push(result);

    expect(renderedKeys(result.host)).toEqual(
      expect.arrayContaining(["income:Salary", "__income_node__", "bucket:FOOD", "__savings__"]),
    );
    expect(renderedKeys(result.host)).not.toContain("__available__");
    expect(renderedLinkTitles(result.host)).toEqual(
      expect.arrayContaining(["Salary → Income: $3,000.00", "Income → FOOD: $900.00", "Income → Savings: $2,100.00"]),
    );
  });
});
