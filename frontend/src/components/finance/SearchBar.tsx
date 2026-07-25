import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { applySuggestion, getSearchSuggestions } from "@/lib/api/client";
import type { SearchSuggestion } from "@/lib/api/types";

/**
 * Discoverable search: focusing the empty field shows the list of things you can
 * filter on, so the syntax never has to be memorized (recognition over recall).
 * Parsing is server-side — see docs/transaction-search-spec.md.
 */
export function SearchBar({
  value,
  onChange,
  placeholder = "Search or filter…",
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keep the committed query and the in-progress text in step, debounced so
  // typing doesn't hammer the API.
  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (draft !== value) onChange(draft);
    }, 250);
    return () => clearTimeout(timer);
  }, [draft]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const suggestions = useQuery({
    queryKey: ["search-suggestions", draft],
    queryFn: () => getSearchSuggestions(draft),
    enabled: open || sheetOpen,
  });

  const accept = (s: SearchSuggestion) => {
    const next = applySuggestion(draft, suggestions.data?.replace_token ?? "", s.value);
    setDraft(next);
    onChange(next);
    inputRef.current?.focus();
    // Picking a field leaves the token open, so keep suggesting values.
    setOpen(true);
  };

  const clear = () => {
    setDraft("");
    onChange("");
    setOpen(false);
  };

  const items = suggestions.data?.suggestions ?? [];
  const isFieldMenu = suggestions.data?.context === "field";

  return (
    <div ref={containerRef} className="relative flex-1">
      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onFocus={() => setOpen(true)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setOpen(false);
              if (e.key === "Enter") {
                onChange(draft);
                setOpen(false);
              }
            }}
            placeholder={placeholder}
            aria-label="Search transactions"
            className="h-10 w-full rounded-md border border-input bg-background pl-8 pr-8 text-sm"
          />
          {draft ? (
            <button
              onClick={clear}
              aria-label="Clear search"
              className="absolute right-1.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded hover:bg-secondary"
            >
              <X className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
          ) : null}
        </div>
        <button
          onClick={() => setSheetOpen(true)}
          aria-label="Show filters"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-input hover:bg-secondary md:hidden"
        >
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>

      {/* Dropdown: fields when between tokens, real values inside one. */}
      {open && items.length > 0 ? (
        <div className="absolute left-0 right-0 top-11 z-40 overflow-hidden rounded-md border border-border bg-background shadow-lg">
          <div className="border-b border-border px-3 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {isFieldMenu ? "Filter by" : `Values for ${suggestions.data?.field}`}
          </div>
          <ul className="max-h-64 overflow-y-auto">
            {items.map((s) => (
              <li key={s.value}>
                <button
                  onClick={() => accept(s)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm hover:bg-secondary"
                >
                  <span className="min-w-0 truncate font-medium">{s.label}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{s.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Mobile tray: same facets, browsable instead of typed. */}
      {sheetOpen ? (
        <>
          <div className="fixed inset-0 z-40 bg-foreground/20" onClick={() => setSheetOpen(false)} aria-hidden />
          <aside
            className="fixed inset-x-0 bottom-0 z-50 max-h-[70vh] overflow-y-auto rounded-t-lg border-t border-border bg-background shadow-xl"
            role="dialog"
            aria-label="Filters"
          >
            <div className="sticky top-0 flex items-center justify-between border-b border-border bg-background px-4 py-3">
              <span className="text-sm font-semibold">Filter by</span>
              <button
                onClick={() => setSheetOpen(false)}
                className="grid h-8 w-8 place-items-center rounded-md hover:bg-secondary"
                aria-label="Close filters"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <ul className="divide-y divide-border">
              {items.map((s) => (
                <li key={s.value}>
                  <button
                    onClick={() => {
                      accept(s);
                      if (!s.has_values) setSheetOpen(false);
                    }}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-secondary"
                  >
                    <span className="min-w-0 truncate font-medium">{s.label}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{s.hint}</span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        </>
      ) : null}
    </div>
  );
}

/** Active filter chips parsed from the query string, each removable. */
export function SearchChips({
  query,
  onChange,
}: {
  query: string;
  onChange: (next: string) => void;
}) {
  const tokens = splitTokens(query);
  if (!tokens.length) return null;

  const remove = (index: number) => onChange(tokens.filter((_, i) => i !== index).join(" "));

  return (
    <div className="mb-3 flex flex-wrap items-center gap-1.5">
      {tokens.map((token, i) => (
        <span
          key={`${token}-${i}`}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary/60 py-0.5 pl-2 pr-1 text-xs"
        >
          {chipLabel(token)}
          <button
            onClick={() => remove(i)}
            aria-label={`Remove filter ${token}`}
            className="grid h-4 w-4 place-items-center rounded-full hover:bg-background"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <button
        onClick={() => onChange("")}
        className="ml-1 text-xs text-muted-foreground underline hover:text-foreground"
      >
        Clear all
      </button>
    </div>
  );
}

/** Split on spaces but keep quoted values ("blue bottle") together. */
export function splitTokens(query: string): string[] {
  const matches = query.match(/(?:[^\s"]+|"[^"]*")+/g);
  return matches ? matches.filter(Boolean) : [];
}

const FIELD_LABEL: Record<string, string> = {
  merchant: "Merchant",
  category: "Category",
  cat: "Category",
  account: "Account",
  from: "From",
  to: "To",
  is: "",
};

export function chipLabel(token: string): string {
  if (token.startsWith(">")) return `Over $${token.slice(1)}`;
  if (token.startsWith("<")) return `Under $${token.slice(1)}`;
  const idx = token.indexOf(":");
  if (idx > 0) {
    const key = token.slice(0, idx).toLowerCase();
    const value = token.slice(idx + 1).replace(/^"|"$/g, "");
    if (key in FIELD_LABEL) {
      const label = FIELD_LABEL[key];
      return label ? `${label}: ${value}` : value;
    }
  }
  return token;
}
