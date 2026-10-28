import { useCallback, useState } from "react";

const KEY = "vibeledger.prior-period-count";
/** Common saved chart preference; defaults to two prior periods on first use. */
export function usePriorPeriodCount(): readonly [number, (count: number) => void] {
  const [count, setCount] = useState<number>(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw !== null && ["0", "1", "2", "3"].includes(raw)) return Number(raw);
    } catch { /* storage may be disabled; keep app functional */ }
    return 2;
  });
  const update = useCallback((next: number) => {
    if (!Number.isInteger(next) || next < 0 || next > 3) return;
    setCount(next);
    try { window.localStorage.setItem(KEY, String(next)); } catch { /* optional preference */ }
  }, []);
  return [count, update] as const;
}
