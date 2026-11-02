import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAccountsSummary } from "@/lib/api/client";

const STORAGE_KEY = "vibeledger.accountScope";

type Listener = () => void;
const listeners = new Set<Listener>();

function readStored(): number[] | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length && parsed.every((v) => typeof v === "number")
      ? parsed
      : null;
  } catch {
    return null;
  }
}

let state: number[] | null = readStored();

function emit() {
  for (const listener of listeners) listener();
}

/** null means "all accounts" — the default, unscoped behavior. */
export function getAccountScope(): number[] | null {
  return state;
}

export function setAccountScope(ids: number[] | null) {
  state = ids && ids.length ? ids : null;
  try {
    if (state) localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable (private browsing, etc.) — in-memory state still works */
  }
  emit();
}

function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Persisted, app-wide account filter shared by every screen. */
export function useAccountScope(): [number[] | null, (ids: number[] | null) => void] {
  const ids = useSyncExternalStore(subscribe, getAccountScope, () => null);
  return [ids, setAccountScope];
}

function quoteToken(value: string): string {
  return value.includes(" ") ? `"${value}"` : value;
}

/** The current account scope translated into `account:` search tokens —
 *  `/transactions` has no `account_ids` param, so this reuses its existing
 *  `q=` grammar instead of adding a second filtering mechanism. Empty string
 *  when unscoped. Shares the AppShell selector's cached accounts query, so
 *  this costs no extra request. */
export function useAccountScopeQuery(): string {
  const [ids] = useAccountScope();
  const accounts = useQuery({ queryKey: ["accounts-summary"], queryFn: getAccountsSummary });
  if (!ids || !ids.length) return "";
  const flat = Object.values(accounts.data?.groups ?? {}).flat();
  const names = ids
    .map((id) => flat.find((a) => a.id === id)?.display_name)
    .filter((n): n is string => Boolean(n));
  return names.map((n) => `account:${quoteToken(n)}`).join(" ");
}
