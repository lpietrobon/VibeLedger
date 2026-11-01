// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import SankeyChart from "./SankeyChart";
import type { CashflowSankey } from "@/lib/api/types";

const data = {
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
  buckets: [{ bucket: "FOOD", amount: 90, categories: [{ category: "FOOD", amount: 90 }] }],
  incomeSources: [{ category: "INCOME", amount: 3000 }],
} satisfies CashflowSankey;

describe("SankeyChart refund credits", () => {
  let host: HTMLDivElement | undefined;

  afterEach(() => {
    host?.remove();
  });

  it("renders net refund credits instead of disabling the chart", () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    act(() => root.render(<SankeyChart data={data} expanded={null} onToggle={() => {}} />));

    expect(host.textContent).toContain("Net refund credits");
    expect(host.textContent).toContain("Not income");
    expect(host.textContent).not.toContain("cannot faithfully show refund credits");
    act(() => root.unmount());
  });
});
