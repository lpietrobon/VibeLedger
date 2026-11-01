# The spirit of this epic

VibeLedger's existing product should feel coherent and dependable. There should
not be a second, obsolete interface competing with the React application, and the
same kind of information should behave consistently wherever it appears. Known
visual defects and contradictory presentation should disappear rather than become
permanent background friction.

When imported data is wrong or ambiguous, the user must be able to correct the
ledger without destroying its history. Two source records that represent one real
transaction can be related explicitly, one retained as the canonical record and
the other omitted from financial totals, and that decision can be inspected and
reversed. Mere similarity is never enough to hide a transaction automatically.

Cashflow views must continue to follow the linked-account boundary established by
the trustworthy-cashflow work. A purchase counts as spending; paying the linked
credit card does not count it again once the transfer is confirmed. If a payment
still contributes because it is unresolved or its counterpart is missing, the
product should expose that uncertainty instead of masking it with a special case.
The same principle applies to movements between any linked accounts, regardless
of account type or institution. Strong, deterministic, two-sided evidence may
resolve an unambiguous transfer automatically, but a label on one transaction is
never sufficient and uncertain matches must remain counted and correctable.

Success is an existing deterministic product with fewer paths, fewer
inconsistencies, and fewer opportunities to misread the ledger. The implementation
may change substantially, but auditability, reversibility, conservative treatment
of ambiguity, and agreement between visible totals and their evidence must remain.
