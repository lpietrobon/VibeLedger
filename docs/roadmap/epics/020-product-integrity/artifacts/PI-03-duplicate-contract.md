# PI-03 — Manual duplicate-correction contract

This contract defines a deliberate correction for two imported records that the
user has established are one real-world transaction. It does not detect or hide
possible duplicates automatically.

## Product outcome

When VibeLedger shows two imported charges but the source statement contains one,
the user can select those two records, identify which is the canonical record,
and mark the other one as its duplicate. Both source records remain visible and
auditable. Only the explicitly selected duplicate stops contributing to financial
reporting. The user can reverse the decision at any time.

This is an economic correction, not an import-identity mechanism. Replaying one
provider transaction ID, or replacing a pending provider record with its posted
successor, remains the synchronization path described in CF-02 and CF-05.
Different provider IDs that merely look alike remain separate transactions until
the user makes this explicit decision.

## Relationship and eligibility

An active correction is a structured, directional relationship between exactly
two current imported records:

- one **canonical** record remains the reporting representative;
- one **duplicate** record is retained as source evidence but excluded from
  accounting; and
- the relationship records that it was manually created, reversed, or
  invalidated, so a note is never its source of truth.

The initial correction scope is intentionally conservative. Creation must reject
the selection unless all of the following are true:

| Requirement | Rule |
|---|---|
| Selection | Exactly two distinct current transaction records; the user explicitly chooses which is canonical. |
| Posting | Both records are posted, not pending. Pending-to-posted replacement belongs to sync identity handling. |
| Account | Both belong to the same linked account. Cross-account movements require transfer reconciliation or an account-coverage decision, never duplicate exclusion. |
| Direction and amount | Both have the same signed amount, using the provider ledger convention. An expense cannot be paired with a receipt. |
| Currency | Both have the same known reporting currency. Unknown, conflicting, unofficial, or different currencies are not eligible. |
| Existing relationships | Neither record is already canonical or duplicate in an active correction. Reverse the prior decision before making another. |
| Transfer state | Neither record participates in a confirmed or unconfirmed transfer pair. A transfer candidate must be resolved through the transfer workflow first. |
| Refund state | Neither record is a confirmed/likely refund, is linked to a refund as its purchase, or has an unresolved refund match. Resolve or clear that relationship first. |
| Provider identity | The records have different current provider transaction identities. A repeated identity is an import replay, not a manual duplicate. |

Matching description, merchant, date, or category is useful context for the
person making the decision but is never a validation rule or automatic trigger.
The same-account restriction is a deliberate v1 product boundary, not a claim
that cross-account duplicates cannot exist.

## Accounting and visibility

All reporting uses the current active relationship at query time; VibeLedger does
not maintain immutable financial snapshots. A correction therefore changes past
period reports when the affected records fall in those periods. The relationship
and its decision history remain available to explain the change.

| Surface or calculation | Before marking | Active correction | After reversal |
|---|---|---|---|
| Spending, income, net cashflow, category totals, monthly/yearly comparisons, and Sankey | Both posted records use their normal treatment. | Canonical record uses normal treatment; duplicate contributes zero. | Both return to normal treatment. |
| Category allocation | Each record uses its own effective category. | Only the canonical record's effective category contributes. The duplicate's category remains visible as source evidence. | Each returns to its own effective category. |
| Recurring detection and recurring totals | Both eligible records may be considered. | Only the canonical record may be considered. | Both may be considered again. |
| Refund and transfer detection | Normal rules apply. | The active duplicate is not a candidate or counterparty. Creation already requires no current relationship. | Normal rules apply again. |
| Aggregate drilldown | Includes the records represented by the aggregate. | Includes the canonical record and excludes the duplicate, so the Activity population reproduces the aggregate. | Includes both again. |
| Ordinary Activity/search/review | Both source records are visible and searchable. | Both remain visible and searchable, labelled **Canonical** and **Marked duplicate** and linked to one another. Raw source-record counts must not be presented as financial counts. | Both remain visible without the relationship label. |
| Historical reports | Current query semantics apply. | Past totals reflect the active correction; decision history identifies why. | Past totals return to the normal calculation. |

Other explicit exclusions still apply. For example, a correctly confirmed internal
transfer remains excluded regardless of duplicate state; the eligibility rules
prevent such a relationship from being created in the first place.

## Lifecycle and durability

The structured relationship must survive ordinary reads and category edits. It
must not be stored solely in an annotation, note, client state, or display label.
Both endpoint roles and sufficient source identity/fingerprint evidence must be
retained for audit and lifecycle handling.

| Source event | Required outcome |
|---|---|
| Provider replay of the same identity | No second source row and no change to an active correction. |
| Non-material provider edit, such as merchant spelling or provider category | Keep the active correction; reporting still uses the canonical record. |
| Material edit to either endpoint: account, posting state, signed amount, date, or currency | Make the correction inactive and require review. Both records resume normal accounting until the user confirms a valid correction again. Show a clear “provider changed this correction” status. |
| Provider removes either endpoint | Make the correction inactive, detach the missing source record, retain decision history, and show that it was invalidated. Any surviving record resumes normal accounting. |
| Item removal / relink | Preserve the decision history and endpoint fingerprint evidence. Reapply an active correction only when each endpoint can be matched once, unambiguously, and still passes every eligibility rule; otherwise leave it inactive and visible for review. |
| Startup orphan cleanup or transaction deletion | Never leave an active relationship pointing at a reused or missing transaction ID. Invalidate/detach it before cleanup; retain the audit history where possible. |
| Reversal | Deactivate the relationship without deleting either imported record or decision history. Restore ordinary accounting immediately and make either row eligible for a later, new correction. |

There is no automatic “best guess” reattachment. If identical fingerprints or
multiple candidate records make a relink ambiguous, VibeLedger preserves the
source records and requires the user to decide again.

## Interaction contract

Activity supports selecting records on desktop and mobile. The duplicate action
appears only for a selection of exactly two eligible-looking records; server
validation remains authoritative.

1. The user selects two records and chooses **Mark as duplicates**.
2. A confirmation view shows both source records, their account/date/amount, and
   requires the user to select the canonical record.
3. It states plainly: “Both imported records will remain visible. Only the record
   marked duplicate will be excluded from spending and income totals.”
4. After confirmation, both rows show their relationship and link to each other.
   The canonical row exposes **Reverse duplicate correction**; the duplicate row
   offers the same action with clear context.
5. Reversal confirms that both records will again count normally, then refreshes
   Activity and every dependent aggregate.

The UI must not call the records fraudulent, assert that either charge was
automatically detected as a duplicate, or hide ambiguous same-date/same-amount
transactions. Validation errors identify the incompatible state (for example,
pending, transfer-related, or changed provider amount) and point to the relevant
workflow where one exists.

## Hand-calculated fixture

All amounts use the ledger sign convention: a positive amount is an expense and
a negative amount is income. These rows are USD, posted, and in the same linked
checking account unless stated otherwise.

| ID | Date | Description | Amount | State |
|---|---|---|---:|---|
| `paycheck` | 2026-03-01 | Salary | -100 | ordinary income |
| `market-a` | 2026-03-02 | Market | 25 | selected canonical |
| `market-b` | 2026-03-02 | Market | 25 | selected duplicate |
| `book` | 2026-03-03 | Bookshop | 10 | ordinary expense |
| `coffee-a` | 2026-03-04 | Cafe | 7 | separate real charge |
| `coffee-b` | 2026-03-04 | Cafe | 7 | separate real charge |

Before correction: income is **100**, expenses are **74**, and net cashflow is
**26**. The two coffee rows remain **14** of expense because no correction was
made for them.

After marking `market-a` canonical and `market-b` duplicate: income is **100**,
expenses are **49**, and net cashflow is **51**. The contributing expense set for
an aggregate drilldown is `market-a`, `book`, `coffee-a`, and `coffee-b`; it must
not include `market-b`. Ordinary Activity still displays all six source rows and
labels the two market rows.

After reversal: income, expense, net, category totals, Sankey, recurring input,
and aggregate drilldown all return to the before-correction result: **100**,
**74**, and **26**. A pending `market-b` or a `market-b` already paired as a
transfer must be rejected rather than silently corrected.

## Implementation and test handoff

### PI-15: immutable TDD contract

Create the failing backend/API tests from the fixture and these cases before PI-04
changes production code:

- active canonical/duplicate relationships exclude exactly the duplicate from
  every shared accounting path, category aggregate, Sankey, and recurring input;
- aggregate-origin Activity queries reproduce that contributing population, while
  ordinary Activity retains both labelled source records;
- reversal restores both rows to normal accounting;
- server validation rejects every ineligible combination in the table and does
  not partially create a relationship;
- replays leave the correction unchanged; material modifications, deletion,
  relink ambiguity, and orphan cleanup cannot leave a stale active relationship
  or silently retain an exclusion; and
- two merely similar provider records remain counted until the explicit action.

PI-15 records the tests and their initial failing result. Their behavioral
expectations are immutable once accepted; PI-04 may change product code only.

### PI-04: implementation boundary

Implement a durable, reversible structured relationship; centralize its active
duplicate exclusion in the existing shared accounting path; integrate its
lifecycle into sync, relink, item removal, and orphan cleanup; and expose enough
read/write API data for PI-05. Do not weaken or rewrite PI-15's accepted tests.

### PI-17 and PI-05: interaction boundary

PI-17 freezes client behavior for exact-two selection, canonical choice,
ineligibility feedback, relationship visibility, reversal confirmation, and
aggregate refresh. PI-05 makes those tests pass unchanged on desktop and mobile.

## Decisions and open questions

No unresolved product decision blocks implementation. The deliberate v1 limits
are: same linked account, equal signed amount, same known currency, posted rows,
and no transfer/refund relationship. A later cross-account or fuzzy-matching
experience requires a new contract rather than broadening these rules silently.
