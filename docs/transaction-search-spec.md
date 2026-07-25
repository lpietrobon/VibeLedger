# Transaction search — spec

Addresses issue #12. The problem with a bare query syntax (`cat:`, `account:`, …)
is that it requires **recall**: you must already know the field names. The fix is
not to drop the syntax but to make the search bar *teach* it — every field and
value is offered from a menu, so you **recognize** instead of remembering.

Decisions (locked): **parsing lives server-side**; **amounts are typed**, no slider.

## Archetype

Token/pill search bar with **suggest-on-focus**, backed by a bottom-sheet facet
list on mobile:

- Tapping the empty field immediately drops down the list of filterable fields —
  you never need to know `category:` exists.
- Choosing a field suggests **real values from your data** (actual categories,
  merchants, accounts).
- Applied filters render as removable **chips**, so active state is always visible.
- Plain words still work with no syntax at all (`coffee` → free-text search).

Rejected: query-builder rows (clunky on a phone), bare suggestion pills without a
dropdown (documented low discoverability), natural-language parsing (unpredictable;
possible later as a complement).

## Grammar (server-side, canonical)

A superset of the existing Streamlit power-user syntax, so current habits keep
working. Tokens are space-separated; anything unrecognized becomes free text.

| Token | Meaning |
|---|---|
| `merchant:<text>` | effective merchant contains text |
| `category:<text>` / `cat:<text>` | effective category equals, or is a child of (`FOOD` matches `FOOD/DINING`) |
| `account:<text>` | effective account name contains text |
| `amount>50`, `>50`, `amount<100`, `<100` | absolute amount bounds |
| `from:2026-01`, `from:2026-01-15` | date lower bound (month → first day) |
| `to:2026-03`, `to:2026-03-15` | date upper bound (month → last day) |
| `is:unreviewed` \| `is:reviewed` | annotation reviewed flag |
| `is:uncategorized` | effective category is `uncategorized` |
| `is:refund` | refund_status in (confirmed, likely) |
| `is:pending` | pending transactions |
| bare words | matched against name, merchant, and category |

Quoting is supported for values with spaces: `merchant:"blue bottle"`.

Unknown `field:value` tokens are **not** silently dropped — they fall through to
free text, so a typo still returns something rather than nothing.

## API

**`GET /transactions?q=<query>`** — `q` is now parsed with the grammar above and
applied as real SQL filters (previously it was a naive LIKE over three columns).
Existing `start_date` / `end_date` / `category` params still work and AND together
with the query.

**`GET /transactions/search-suggestions?q=<partial>`** — context-aware suggestions
that drive the dropdown. Returns:

```json
{
  "context": "field" | "value",
  "field": "category",
  "replace_token": "cat:foo",
  "suggestions": [
    { "value": "category:", "label": "Category", "hint": "e.g. FOOD/DINING" }
  ]
}
```

- Empty/most input → `context: "field"`, the full field menu (this is what removes
  the recall burden).
- Cursor inside a `field:` token → `context: "value"`, real distinct values from the
  DB for that field, prefix-filtered.

Value sources: categories from the effective-category expression, merchants from
effective merchant, accounts from effective account name — all deduped, ordered by
frequency, capped (20).

## Client

- `SearchBar` component: input + dropdown + chips.
  - Focus (empty) → field menu. Typing filters it.
  - Selecting a field appends `field:` and immediately re-queries for values.
  - Selecting a value completes the token and re-runs the search.
  - Parsed tokens render as chips below the bar; the X removes just that token.
- Mobile: a filter icon opens a **bottom sheet** listing the same fields → values,
  writing into the same query string (NN/G's tray pattern).
- Debounced (250 ms) so typing doesn't hammer the API.

## Testing

- pytest: parser unit tests (each token type, quoting, unknown-token fallthrough,
  combination) + endpoint tests (filters actually narrow results; suggestions
  return fields when empty and values inside a token).
- vitest: client mapping for the suggestions response; token→chip parsing helper.

## Known follow-up

`dashboard_lib.parse_transaction_filter_query` (Streamlit) still has its own local
copy of this grammar, applied to a pandas DataFrame. It is now the *second*
implementation. Streamlit reads SQLite directly, so unifying it means routing that
page through the API — deliberately out of scope here, but it is the remaining
duplication and should be closed when Streamlit's transactions page is next touched.
