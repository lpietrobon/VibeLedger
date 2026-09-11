// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import SankeyChart from "./SankeyChart";
import type { CashflowSankey } from "@/lib/api/types";

type ViewportFixture = {
  name: "wide" | "narrow";
  width: number;
  height: number;
};

const viewportFixtures: ViewportFixture[] = [
  { name: "wide", width: 1280, height: 900 },
  { name: "narrow", width: 360, height: 760 },
];

const readableNames = [
  "Income",
  "Salary and compensation",
  "Freelance and other income",
  "Available cash",
  "Net refund credits",
  "Deficit funding",
  "FOOD",
  "TRANSPORTATION",
  "Home improvement and household maintenance",
  "Childcare and school activities",
  "Public transit and fuel",
  "Repairs and maintenance",
  "Medical and pharmacy",
  "Savings",
  "Groceries and household supplies",
  "Restaurants and takeaway meals",
];

const expandedFixture = {
  sankeySupported: true,
  visualizationQualification: null,
  negativeCategories: [
    { category: "Home improvement and household maintenance", amount: -120 },
  ],
  positiveNetSpend: 2080,
  income: 3000,
  totalSpend: -1960,
  savings: 1040,
  deficit: 200,
  netRefundCredits: 120,
  netRefundCreditCategories: [
    { category: "Home improvement and household maintenance", amount: 120 },
  ],
  buckets: [
    {
      bucket: "FOOD",
      amount: 640,
      categories: [
        { category: "Groceries and household supplies", amount: 430 },
        { category: "Restaurants and takeaway meals", amount: 210 },
      ],
    },
    {
      bucket: "TRANSPORTATION",
      amount: 420,
      categories: [{ category: "Public transit and fuel", amount: 420 }],
    },
    {
      bucket: "Home improvement and household maintenance",
      amount: 380,
      categories: [{ category: "Repairs and maintenance", amount: 380 }],
    },
    {
      bucket: "Childcare and school activities",
      amount: 340,
      categories: [{ category: "Childcare and school activities", amount: 340 }],
    },
    {
      bucket: "HEALTH",
      amount: 300,
      categories: [{ category: "Medical and pharmacy", amount: 300 }],
    },
  ],
  incomeSources: [
    { category: "Salary and compensation", amount: 2500 },
    { category: "Freelance and other income", amount: 500 },
  ],
} satisfies CashflowSankey;

const allExpectedNodes = [
  "Income",
  "Salary and compensation",
  "Freelance and other income",
  "Available cash",
  "Net refund credits",
  "Deficit funding",
  "FOOD",
  "TRANSPORTATION",
  "Home improvement and household maintenance",
  "Childcare and school activities",
  "HEALTH",
  "Savings",
  "Groceries and household supplies",
  "Restaurants and takeaway meals",
];

function renderFixture(viewport: ViewportFixture, expanded: string | null = "FOOD") {
  const host = document.createElement("div");
  host.style.width = `${viewport.width}px`;
  host.style.height = `${viewport.height}px`;
  host.dataset.viewport = viewport.name;
  document.body.appendChild(host);
  const toggles: string[] = [];
  const root = createRoot(host);
  act(() => {
    root.render(
      <SankeyChart
        data={expandedFixture}
        expanded={expanded}
        onToggle={(key) => toggles.push(key)}
      />,
    );
  });
  return { host, root, toggles };
}

function nodeForKey(host: HTMLElement, key: string) {
  return host.querySelector(`[data-sankey-key="${key}"]`);
}

function textWidthEstimate(text: SVGTextElement) {
  // Deliberately conservative: this detects labels that would visibly escape
  // the 640-unit viewBox without depending on browser font rasterization.
  return (text.textContent?.length ?? 0) * 7;
}

describe("PI-21 frozen Sankey readability and accessibility contract", () => {
  const rendered: Array<{ host: HTMLDivElement; root: Root }> = [];

  afterEach(() => {
    for (const { root, host } of rendered.splice(0)) {
      act(() => root.unmount());
      host.remove();
    }
  });

  it.each(viewportFixtures)(
    "$name viewport uses at least 12px rendered SVG text for every label and amount",
    (viewport) => {
      const result = renderFixture(viewport);
      rendered.push(result);
      const labels = [...result.host.querySelectorAll<SVGTextElement>("svg text")];

      expect(labels.length).toBeGreaterThan(8);
      for (const label of labels) {
        expect(Number(label.getAttribute("font-size"))).toBeGreaterThanOrEqual(12);
      }
    },
  );

  it("gives expandable nodes stable keys, accessible names, and keyboard activation", () => {
    const result = renderFixture(viewportFixtures[0], null);
    rendered.push(result);

    const income = nodeForKey(result.host, "__income_node__");
    const food = nodeForKey(result.host, "bucket:FOOD");
    expect(income).not.toBeNull();
    expect(food).not.toBeNull();

    for (const node of [income, food]) {
      expect(node?.getAttribute("role")).toBe("button");
      expect(node?.getAttribute("tabindex")).toBe("0");
      expect(node?.getAttribute("aria-label")).toMatch(/\$[\d,]+\.\d{2}/);
    }

    act(() => {
      income?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      food?.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    });
    expect(result.toggles).toEqual(["__income__", "FOOD"]);
  });

  it.each(viewportFixtures)(
    "$name viewport keeps long labels inside the viewBox or exposes truthful truncation",
    (viewport) => {
      const result = renderFixture(viewport);
      rendered.push(result);
      const svg = result.host.querySelector("svg");
      expect(svg?.getAttribute("viewBox")).toMatch(/^0 0 640 \d+$/);

      const labels = [...result.host.querySelectorAll<SVGTextElement>("svg text")];
      for (const label of labels) {
        const fullLabel = label.getAttribute("data-full-label");
        expect(fullLabel).not.toBeNull();
        expect(readableNames).toContain(fullLabel);

        const visible = label.textContent ?? "";
        if (!visible.includes(fullLabel ?? "")) {
          expect(label.getAttribute("aria-label")).toBe(fullLabel);
          expect(label.querySelector("title")?.textContent).toContain(fullLabel ?? "");
        }

        const x = Number(label.getAttribute("x"));
        const width = textWidthEstimate(label);
        if (label.getAttribute("text-anchor") === "end") {
          expect(x - width).toBeGreaterThanOrEqual(0);
        } else {
          expect(x + width).toBeLessThanOrEqual(640);
        }
      }
    },
  );

  it("preserves stable bucket/category keys and exact monetary values through expansion", () => {
    const result = renderFixture(viewportFixtures[0], "FOOD");
    rendered.push(result);

    for (const label of allExpectedNodes.filter(
      (name) => !["Salary and compensation", "Freelance and other income"].includes(name),
    )) {
      expect(result.host.textContent).toContain(label);
    }
    expect(nodeForKey(result.host, "bucket:FOOD")).not.toBeNull();
    expect(nodeForKey(result.host, "cat:Groceries and household supplies")).not.toBeNull();
    expect(nodeForKey(result.host, "cat:Restaurants and takeaway meals")).not.toBeNull();
    expect(result.host.textContent).toContain("$640.00");
    expect(result.host.textContent).toContain("$430.00");
    expect(result.host.textContent).toContain("$210.00");
    expect(result.host.textContent).toContain("$120.00");
    expect(result.host.textContent).toContain("$200.00");

    const incomeResult = renderFixture(viewportFixtures[0], "__income__");
    rendered.push(incomeResult);
    expect(incomeResult.host.textContent).toContain("Salary and compensation");
    expect(incomeResult.host.textContent).toContain("Freelance and other income");
    expect(nodeForKey(incomeResult.host, "income:Salary and compensation")).not.toBeNull();
    expect(nodeForKey(incomeResult.host, "income:Freelance and other income")).not.toBeNull();
  });
});
