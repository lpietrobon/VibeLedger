// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DateRangeSelector } from "./DateRangeSelector";
import { PriorPeriodsControl } from "./PriorPeriodsControl";
import { initialDateSelection } from "@/lib/dateRange";

let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-10-25T12:00:00Z"));
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.useRealTimers();
});

it("uses a single row of preset buttons; a two-tap Custom calendar stays open until both dates", async () => {
  const onChange = vi.fn();
  act(() => root.render(<DateRangeSelector value={initialDateSelection("current-month", "2026-10-25")} onChange={onChange} />));
  for (const label of ["30D","1Y","Month","Year","Custom"]) {
    expect(container.querySelector('button[aria-label="' + label + ' period"]')).not.toBeNull();
  }
  expect(container.querySelector('select[aria-label="Comparison rule"]')).toBeNull();
  expect(container.querySelector('input[aria-label="From date"]')).toBeNull();
  await act(async () => (container.querySelector('button[aria-label="Custom period"]') as HTMLButtonElement).click());
  expect(container.querySelector('[role="dialog"]')).not.toBeNull();
  await act(async () => (container.querySelector('button[aria-label="2026-10-06"]') as HTMLButtonElement).click());
  expect(container.textContent).toContain("Now select the end date");
  expect((Array.from(container.querySelectorAll("button")).find((x) => x.textContent === "Apply") as HTMLButtonElement).disabled).toBe(true);
  await act(async () => (container.querySelector('button[aria-label="2026-10-18"]') as HTMLButtonElement).click());
  expect(container.querySelector('[role="dialog"]')).not.toBeNull();
  await act(async () => (Array.from(container.querySelectorAll("button")).find((x) => x.textContent === "Apply") as HTMLButtonElement).click());
  expect(container.querySelector('[role="dialog"]')).toBeNull();
  expect(onChange).toHaveBeenCalledWith({
    preset: "custom", startDate: "2026-10-06", endDate: "2026-10-18", comparison: "previous-period",
  });
});

it("exposes compact 0,1,2,3 buttons with an accessible active state", async () => {
  const onChange = vi.fn();
  act(() => root.render(<PriorPeriodsControl value={2} onChange={onChange}/>));
  expect(container.querySelector('button[aria-label="2 prior periods"]')?.getAttribute("aria-pressed")).toBe("true");
  expect(container.querySelectorAll("button").length).toBe(4);
  await act(async () => (container.querySelector('button[aria-label="0 prior periods"]') as HTMLButtonElement).click());
  expect(onChange).toHaveBeenCalledWith(0);
});
