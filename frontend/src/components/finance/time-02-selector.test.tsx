// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DateRangeSelector } from "./DateRangeSelector";
import { initialDateSelection } from "@/lib/dateRange";
let root: Root; let container: HTMLDivElement;
beforeEach(() => {
 Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
 vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-25T12:00:00Z"));
 container = document.createElement("div"); document.body.appendChild(container); root = createRoot(container);
});
afterEach(() => { act(() => root.unmount()); container.remove(); vi.useRealTimers(); });
it("exposes independent four-rule control and literal From/To", () => {
 act(() => root.render(<DateRangeSelector value={initialDateSelection("current-month", "2026-10-25")} onChange={vi.fn()} />));
 const select = container.querySelector('select[aria-label="Comparison rule"]') as HTMLSelectElement;
 expect(select).not.toBeNull();
 expect(Array.from(select.options).map(o => o.value)).toEqual(["none", "previous-month", "previous-year", "previous-period"]);
 expect((container.querySelector('input[aria-label="From date"]') as HTMLInputElement)?.value).toBe("2026-10-01");
 expect((container.querySelector('input[aria-label="To date"]') as HTMLInputElement)?.value).toBe("2026-10-25");
});
it("changing preset preserves None", () => {
 const onChange = vi.fn();
 act(() => root.render(<DateRangeSelector value={initialDateSelection("current-month", "2026-10-25")} onChange={onChange} />));
 act(() => (container.querySelector('button[aria-label="1Y period"]') as HTMLButtonElement).click());
 expect(onChange).toHaveBeenCalledWith({ preset: "last-365", startDate: "2025-10-26", endDate: "2026-10-25", comparison: "none" });
});
it("Activity suppresses comparator, not custom bounds", () => {
 act(() => root.render(<DateRangeSelector value={initialDateSelection("all", "2026-10-25")} onChange={vi.fn()} allowAll allowComparison={false} />));
 expect(container.querySelector('select[aria-label="Comparison rule"]')).toBeNull();
 expect(container.querySelector('input[aria-label="From date"]')).not.toBeNull();
 expect(container.querySelector('input[aria-label="To date"]')).not.toBeNull();
});
it("labels mapped bounds and unequal inclusive durations", () => {
 act(() => root.render(<DateRangeSelector value={{ preset: "custom", startDate: "2026-03-29", endDate: "2026-03-31", comparison: "previous-month" }} onChange={vi.fn()} />));
 expect(container.textContent).toContain("2026-03-29");
 expect(container.textContent).toContain("2026-03-31");
 expect(container.textContent).toContain("2026-02-28");
 expect(container.textContent).toMatch(/3 days.*1 day/);
});
it("independent comparison choice leaves selected dates untouched", () => {
 const onChange = vi.fn();
 act(() => root.render(<DateRangeSelector value={{ preset: "custom", startDate: "2026-10-05", endDate: "2026-10-15", comparison: "none" }} onChange={onChange} />));
 const select = container.querySelector('select[aria-label="Comparison rule"]') as HTMLSelectElement;
 expect(select).not.toBeNull();
 act(() => { select.value = "previous-year"; select.dispatchEvent(new Event("change", { bubbles: true })); });
 expect(onChange).toHaveBeenCalledWith({ preset: "custom", startDate: "2026-10-05", endDate: "2026-10-15", comparison: "previous-year" });
});
