# CF-09 — review capability inventory

Completed 2026-09-07. This is the boundary for the existing review experience;
it does not claim a generalized duplicate-charge or fraud detector.

| Situation | Existing evidence and action | Accounting effect |
|---|---|---|
| Replayed import | Transaction identity/fingerprint handling from CF-05 prevents the duplicate ingestion row; it is not presented as a merchant charge | No extra row enters reporting |
| Possible internal transfer | Two account-side records, dates, amount and detector source; user can confirm or unpair | Counted until confirmed; confirmed pair is excluded |
| Refund | Refund status, matched transaction id/reason where available, and manual status control | Refund nets in its posted period; not income or a subscription |
| Category question | Original bank description/category, current mapping source, and editable override | Allocation changes; the transaction remains recorded |
| Recurring payment | Posted-charge occurrences, cadence, range/average, last/next date, account/category and active/canceled override | Estimate only; transfers/refunds are excluded from detection |
| Repeated charge / suspicious charge | **No detector is implemented.** Same-size purchases alone are not presented as suspicious or duplicate | No row is removed or excluded by this UI |

## Interaction contract

Saving an annotation waits for the API result. A failure leaves the sheet and the
user's inputs open with an alert; a success closes the sheet and invalidates ledger
views. Confirming a transfer announces that it was excluded; unpairing announces that
only the relationship was removed. These outcomes persist through refresh/resync via
the existing annotation fingerprints and rejected-pair memory.

Recurring status changes are also explicit, persisted overrides. The UI labels all
cost values as estimates inferred from posted charges and carries the server's
history-coverage qualification.

The deliberate product decision is to defer repeated-charge/suspicion detection to a
separate, evidence-first scope (future FI-03/FI-06 work). CF-09 must never use that
absence to imply that every real charge has been inspected or that a user is fraud-safe.
