import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, ChevronRight, Plus, Search, Tag, X } from "lucide-react";
import { Sheet } from "@/components/layout/Sheet";
import { CATEGORIES, getCategoryCatalog } from "@/lib/api/client";
import type { CategoryEntry } from "@/lib/api/types";

/**
 * Hierarchical category picker.
 *
 * Search-first with grouping: "Most used" is pinned for the one-tap case,
 * parents collapse their children so the list stays short, and typing filters
 * across the whole tree. New categories are created inline.
 *
 * PARENT/CHILD is a convention, not an invariant — 1-level values (unmapped
 * Plaid primaries) and 3+-level values are both legitimate, so nothing here
 * assumes a depth.
 *
 * The exported helpers below hold all the logic; they are unit tested directly
 * (repo convention — see SearchBar.test.ts).
 */

export type CategoryNode = {
  value: string;
  label: string;
  count: number;
  totalCount: number;
  children: CategoryNode[];
  /** false = a parent inferred from a child path, never used on its own. */
  exists: boolean;
};

/** Canonical form. Mirrors normalize_category() in app/services/category_catalog.py. */
export function normalizeCategory(value: string): string {
  return value.trim().replace(/\s+/g, "_").replace(/\/+/g, "/").toUpperCase();
}

export function parentOf(value: string): string {
  const i = value.lastIndexOf("/");
  return i > 0 ? value.slice(0, i) : "";
}

export function leafLabel(value: string): string {
  const i = value.lastIndexOf("/");
  return i >= 0 ? value.slice(i + 1) : value;
}

/** Group a flat catalog into a tree, synthesizing any missing ancestors. */
export function buildCategoryTree(entries: CategoryEntry[]): CategoryNode[] {
  const nodes = new Map<string, CategoryNode>();

  const ensure = (path: string): CategoryNode => {
    const existing = nodes.get(path);
    if (existing) return existing;
    const node: CategoryNode = {
      value: path,
      label: leafLabel(path),
      count: 0,
      totalCount: 0,
      children: [],
      exists: false,
    };
    nodes.set(path, node);
    const parent = parentOf(path);
    if (parent) ensure(parent).children.push(node);
    return node;
  };

  for (const entry of entries) {
    const value = normalizeCategory(entry.value);
    if (!value) continue;
    const node = ensure(value);
    node.exists = true;
    node.count += entry.count;
  }

  // Roll counts up so a collapsed parent can show its subtree total.
  const roll = (node: CategoryNode): number => {
    node.totalCount = node.count + node.children.reduce((sum, c) => sum + roll(c), 0);
    node.children.sort((a, b) => b.totalCount - a.totalCount || a.value.localeCompare(b.value));
    return node.totalCount;
  };

  const roots = [...nodes.values()].filter((n) => !parentOf(n.value));
  roots.forEach(roll);
  roots.sort((a, b) => b.totalCount - a.totalCount || a.value.localeCompare(b.value));
  return roots;
}

/**
 * Rank a category against a search needle.
 * Higher is better; 0 means no match. Space and "/" are interchangeable so
 * "food din", "food/din" and "din" all reach FOOD/DINING.
 */
export function scoreCategory(value: string, needle: string): number {
  if (!needle) return 1;
  const haystack = value.toUpperCase();
  const target = normalizeCategory(needle).replace(/_/g, "/");
  if (!target) return 1;
  const leaf = leafLabel(haystack);

  if (haystack === target) return 100;
  if (leaf === target) return 90;
  if (leaf.startsWith(target)) return 70;
  if (haystack.startsWith(target)) return 60;
  if (haystack.includes(target)) return 40;
  // Fall back to matching each fragment anywhere ("food sushi" -> FOOD/DINING/SUSHI).
  const parts = target.split("/").filter(Boolean);
  if (parts.length > 1 && parts.every((p) => haystack.includes(p))) return 20;
  return 0;
}

export function filterCategories(entries: CategoryEntry[], query: string): CategoryEntry[] {
  if (!query.trim()) return entries;
  return entries
    .map((entry) => ({ entry, score: scoreCategory(entry.value, query) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || b.entry.count - a.entry.count)
    .map((row) => row.entry);
}

/** Top N actually-used categories — the pinned one-tap section. */
export function recentCategories(entries: CategoryEntry[], limit = 6): CategoryEntry[] {
  return entries
    .filter((e) => e.count > 0)
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

/**
 * What "create" should offer for the current input, or null if there's nothing
 * to create. A typed value containing "/" is absolute; otherwise it's created
 * under the parent currently drilled into.
 */
export function createSuggestion(
  rawInput: string,
  path: string,
  entries: CategoryEntry[],
): string | null {
  const typed = normalizeCategory(rawInput);
  if (!typed) return null;
  const candidate = typed.includes("/") || !path ? typed : normalizeCategory(`${path}/${typed}`);
  const exists = entries.some((e) => normalizeCategory(e.value) === candidate);
  return exists ? null : candidate;
}

function findNode(nodes: CategoryNode[], path: string): CategoryNode | null {
  for (const node of nodes) {
    if (node.value === path) return node;
    const hit = findNode(node.children, path);
    if (hit) return hit;
  }
  return null;
}

const FALLBACK: CategoryEntry[] = CATEGORIES.map((value) => ({
  value,
  count: 0,
  source: "default" as const,
}));

export function CategoryPicker({
  value,
  onChange,
  placeholder = "Choose a category",
  allowClear = false,
  clearLabel = "Inherit from rules/Plaid",
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  /** Adds a row that clears the override (emits ""). */
  allowClear?: boolean;
  clearLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [path, setPath] = useState("");
  const queryClient = useQueryClient();

  const catalog = useQuery({
    queryKey: ["category-catalog"],
    queryFn: getCategoryCatalog,
    enabled: open,
    staleTime: 5 * 60 * 1000,
  });

  // Never show an empty picker: fall back to the bundled defaults offline.
  const entries = catalog.data?.length ? catalog.data : FALLBACK;
  const tree = useMemo(() => buildCategoryTree(entries), [entries]);
  const searching = search.trim().length > 0;
  const matches = useMemo(
    () => (searching ? filterCategories(entries, search).slice(0, 50) : []),
    [entries, search, searching],
  );
  const mostUsed = useMemo(() => recentCategories(entries), [entries]);
  const creatable = createSuggestion(search, path, entries);
  const currentNode = path ? findNode(tree, path) : null;
  const visibleNodes = currentNode ? currentNode.children : tree;

  const close = () => {
    setOpen(false);
    setSearch("");
    setPath("");
  };

  const choose = (next: string) => {
    const canonical = next ? normalizeCategory(next) : "";
    if (canonical && !entries.some((e) => normalizeCategory(e.value) === canonical)) {
      // Keep a just-created value available without waiting for a refetch.
      queryClient.setQueryData<CategoryEntry[]>(["category-catalog"], (prev) => [
        ...(prev ?? []),
        { value: canonical, count: 0, source: "default" },
      ]);
    }
    onChange(canonical);
    close();
  };

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex h-10 min-w-0 flex-1 items-center justify-between gap-2 rounded-md border border-input bg-background px-2.5 text-left text-sm"
        >
          <span className="flex min-w-0 items-center gap-2">
            <Tag className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className={"truncate " + (value ? "" : "text-muted-foreground")}>
              {value || placeholder}
            </span>
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
        {allowClear && value ? (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Clear category"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-input hover:bg-secondary"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        ) : null}
      </div>

      {open ? (
        <Sheet
          level={1}
          widthClass="md:w-[420px]"
          label="Choose a category"
          onClose={close}
          title={
            path ? (
              <button
                onClick={() => setPath(parentOf(path))}
                className="-ml-1 inline-flex items-center gap-1 rounded px-1 hover:bg-secondary"
              >
                <ChevronLeft className="h-4 w-4" />
                {path}
              </button>
            ) : (
              "Category"
            )
          }
          subtitle={path ? "Pick a sub-category, or use the parent" : "Search, browse, or create"}
        >
          <div className="sticky top-0 z-10 border-b border-border bg-background px-4 py-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              {/* No autofocus: on a phone the keyboard would cover the list, and
                  browsing is the common case. Tap to search. */}
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search or type a new category…"
                aria-label="Search categories"
                className="h-10 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm"
              />
            </div>
          </div>

          <ul className="divide-y divide-border">
            {!searching && allowClear ? (
              <Row label={clearLabel} hint="clear override" onClick={() => choose("")} muted />
            ) : null}

            {!searching && value ? (
              <Row label={value} hint="current" selected onClick={() => choose(value)} />
            ) : null}

            {!searching && !path && mostUsed.length ? (
              <>
                <SectionLabel>Most used</SectionLabel>
                {mostUsed.map((entry) => (
                  <Row
                    key={`recent-${entry.value}`}
                    label={entry.value}
                    hint={`${entry.count}`}
                    onClick={() => choose(entry.value)}
                  />
                ))}
              </>
            ) : null}

            {!searching && path && currentNode ? (
              <Row
                label={`Use ${path}`}
                hint={currentNode.exists ? `${currentNode.count}` : "new"}
                onClick={() => choose(path)}
              />
            ) : null}

            {!searching ? (
              <>
                <SectionLabel>{path ? "Sub-categories" : "All categories"}</SectionLabel>
                {visibleNodes.map((node) =>
                  node.children.length ? (
                    <Row
                      key={node.value}
                      label={node.label}
                      hint={`${node.children.length} sub · ${node.totalCount}`}
                      chevron
                      onClick={() => setPath(node.value)}
                    />
                  ) : (
                    <Row
                      key={node.value}
                      label={node.label}
                      hint={`${node.totalCount}`}
                      onClick={() => choose(node.value)}
                    />
                  ),
                )}
              </>
            ) : (
              <>
                <SectionLabel>{matches.length ? "Matches" : "No matches"}</SectionLabel>
                {matches.map((entry) => (
                  <Row
                    key={entry.value}
                    label={leafLabel(entry.value)}
                    hint={parentOf(entry.value) || `${entry.count}`}
                    onClick={() => choose(entry.value)}
                  />
                ))}
              </>
            )}

            {/* Below matches, so a typo never wins by default. */}
            {creatable ? (
              <li>
                <button
                  onClick={() => choose(creatable)}
                  className="flex w-full items-center gap-2 px-4 py-3.5 text-left text-sm hover:bg-secondary"
                >
                  <Plus className="h-4 w-4 shrink-0 text-emerald-700" />
                  <span className="min-w-0 flex-1 truncate">
                    Create <span className="font-semibold">{creatable}</span>
                  </span>
                </button>
              </li>
            ) : null}
          </ul>
        </Sheet>
      ) : null}
    </>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <li className="bg-secondary/40 px-4 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </li>
  );
}

function Row({
  label,
  hint,
  onClick,
  chevron = false,
  selected = false,
  muted = false,
}: {
  label: string;
  hint?: string;
  onClick: () => void;
  chevron?: boolean;
  selected?: boolean;
  muted?: boolean;
}) {
  return (
    <li>
      <button
        onClick={onClick}
        className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left text-sm hover:bg-secondary"
      >
        <span className={"min-w-0 flex-1 truncate " + (muted ? "text-muted-foreground" : "font-medium")}>
          {label}
        </span>
        {selected ? <Check className="h-4 w-4 shrink-0 text-emerald-700" /> : null}
        {hint ? (
          <span className="min-w-0 max-w-[45%] shrink truncate text-right text-xs text-muted-foreground">
            {hint}
          </span>
        ) : null}
        {chevron ? <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" /> : null}
      </button>
    </li>
  );
}
