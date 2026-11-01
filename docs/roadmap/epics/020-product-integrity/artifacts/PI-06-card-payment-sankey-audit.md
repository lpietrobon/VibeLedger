# PI-06 — card-payment Sankey audit

## Investigation identity and privacy boundary

This RCA inspected the owner-operated local VibeLedger instance at commit
`7c39934446453d0bed88f2158a30ee73ff020404` on branch
`roadmap/product-integrity-inspectability`. The environment was the active local
FastAPI/React deployment backed by its local SQLite ledger, with production Plaid
mode and mock data disabled. Hostnames, account names and masks, merchant strings,
provider transaction IDs, database IDs, and other private row data are omitted.

The Insights page initializes to the selected `90d` control. At investigation time
(2026-09-09 PDT), its exact inclusive request bounds were **2026-06-12 through
2026-09-09**. The live response inspected was:

```text
GET /analytics/cashflow-sankey?start_date=2026-06-12&end_date=2026-09-09
```

The exact response category was `FINANCE/CREDIT_CARD_PAYMENT`, not an inferred UI
label. It was produced by the effective rule category on the relevant rows. The
provider detail on all but two counterpart-side rows was the provider's credit-card
payment detail; all relevant descriptions independently carried a payment signal.

## Sankey and Activity evidence

### Before/after totals

| Measurement | Before review action | After review action |
| --- | ---: | ---: |
| `FINANCE/CREDIT_CARD_PAYMENT` | $16,746.41 | Not applicable |
| `FINANCE` bucket | $47,111.58 | Not applicable |
| Positive net spend / total spend | $89,034.75 | Not applicable |
| Income | $95,295.20 | Not applicable |

No confirmation was performed. None of the 13 category rows had an unconfirmed
`TransferPair`; creating a pair during this RCA would alter the evidence and violate
the instruction not to silently create one. Accordingly, there is no truthful
post-confirmation total to report. The database remained unchanged and card
purchases remained counted under the same accounting state.

Activity was queried with the identical dates and exact category. All **13 rows on
3 pages** were inspected (`limit=5`, offsets 0/5/10, page sizes 5/5/3). Five were
negative card-side payment credits with `expense_amount = 0`; the eight positive
checking-side rows below sum exactly to the Sankey category total. All 13 rows were
posted, on active linked USD accounts, not active duplicates, and had no
`TransferPair`.

### Anonymized contributing-row classification

Plaid's sign convention is used: positive amounts leave the account. “Counterpart”
means an exact opposite-signed amount on another active linked account anywhere in
the locally recorded history. Account aliases distinguish the two linked credit
cards without exposing names or masks. Exact private row dates and amounts were
checked locally but are deliberately not reproduced here.

| Row | Account | Pending | Pair state | Counterpart evidence | `expense_amount` / Sankey | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| C01 | linked checking | no | none | exact opposite on linked card A, posted 3 days earlier | positive / yes | **3 — detection gap** |
| C02 | linked checking | no | none | no exact opposite row in linked history | positive / yes | **4 — coverage/history limitation** |
| C03 | linked checking | no | none | exact opposite on linked card B, posted 2 days earlier | positive / yes | **3 — detection gap** |
| C04 | linked checking | no | none | exact opposite on linked card A, posted 2 days earlier | positive / yes | **3 — detection gap** |
| C05 | linked checking | no | none | no exact opposite row in linked history | positive / yes | **4 — coverage/history limitation** |
| C06 | linked checking | no | none | no exact opposite row in linked history | positive / yes | **4 — coverage/history limitation** |
| C07 | linked checking | no | none | exact opposite on linked card B, posted 4 days earlier | positive / yes | **3 — detection gap** |
| C08 | linked checking | no | none | exact opposite on linked card A, posted 4 days earlier | positive / yes | **3 — detection gap** |

Classification totals:

| Required classification | Rows | Sankey amount |
| --- | ---: | ---: |
| 1. Confirmed transfer | 0 | $0.00 |
| 2. Unconfirmed transfer candidate | 0 | $0.00 |
| 3. Unpaired, counterpart exists in linked history | 5 | $14,445.00 |
| 4. Unpaired, counterpart absent from linked history | 3 | $2,301.41 |
| 5. Actual shared-accounting regression | 0 | $0.00 |

## Observed facts

1. The five class-3 rows each have one exact, opposite-signed, posted counterpart
   on an active linked credit-card account in the same currency. Their structural
   category/description evidence identifies both sides as card-payment activity.
2. In every class-3 case, the card-side credit posted **before** the checking-side
   outflow: 2 or 3 days earlier for three rows and 4 days earlier for two rows.
3. `validate_pair()` requires the positive outflow to post on or before the negative
   inflow. Therefore all five real shapes fail validation with a negative directed
   gap. The August rows would also exceed the auto detector's default 3-day window.
   Current detection rules should **not** have found these rows as written; the
   observed posting order is outside their evidence model.
4. The three class-4 rows have no exact opposite-signed row on any other locally
   linked account in the available ledger history. Reporting metadata explicitly
   marks history coverage as unverified.
5. No relevant row was pending, duplicated, confirmed, or even paired as a pending
   candidate. The shared Sankey query correctly retained all eight unresolved
   positive rows and summed `expense_amount()` to $16,746.41.
6. A confirmed pair would be excluded by the same shared `posted_activity(...,
   include_transfers=False)` predicate used outside Sankey. The focused regression
   suite still proves the linked-card baseline; no private row contradicted it.

## Hypotheses (not promoted to facts)

- The five class-3 shapes are genuine internal card repayments. Exact amount,
  opposite sign, checking-to-credit account roles, common currency, payment
  classification, and recurring posting pattern make this strongly supported, but
  they remain unresolved until a person confirms a candidate.
- The three class-4 outflows may have counterparts in unlinked accounts, outside
  imported history, or represented by non-exact/split postings. Local evidence
  cannot choose among those explanations and must not label them transfers.
- The detector's directed-date assumption appears too narrow for real credit-card
  settlement ordering. That is a detection/review defect, not evidence that
  accounting should suppress a category by name.

## Conclusion

The material category is explained entirely by **class 3 (transfer-detection gap)**
and **class 4 (coverage/history limitation)**. It is not a shared-accounting
regression. The previous code-level conclusion—that confirmed transfers are
excluded while unresolved rows are conservatively counted—is upheld, not
contradicted; PI-06 does not need to be reopened. This private-row RCA completes
the evidence that the earlier audit could not access.

## Recommendation for PI-19 and PI-07

### PI-19: freeze this hand-checkable fixture

Use synthetic values only; do not copy private dates, amounts, descriptions, or
identifiers.

1. Create active linked USD checking and credit-card accounts.
2. On day D, post a card purchase of **+$30** in `FOOD/DINING` and a card-payment
   credit of **−$100** in `FINANCE/CREDIT_CARD_PAYMENT`.
3. On D+2, post the matching checking outflow of **+$100** in
   `FINANCE/CREDIT_CARD_PAYMENT`. Both payment rows are posted, exact opposites,
   uniquely closest, and initially unpaired.
4. Before resolution, assert the detector creates exactly one **unconfirmed**
   candidate despite the reverse posting order; Activity exposes both sides as
   candidates. This assertion is red at audited commit `7c39934`.
5. Preserve conservative accounting while unresolved: the +$100 payment remains
   spending and the −$100 side remains income under current policy.
6. Confirm through the transfer API/workflow. Assert both payment rows then
   contribute zero income, zero spending, and no Sankey expense category, while
   the +$30 card purchase remains exactly once.
7. Add a separate **+$60** checking payment with no opposite row. Assert no pair is
   invented, it remains counted, and Activity/reporting evidence communicates that
   linked history cannot establish a transfer.

Exercise both aggregate Sankey payloads and Activity evidence (`is_transfer`,
`is_transfer_candidate`, category, and pair state) with literal totals.
Retain the conservative generic collision contract currently named
`test_inflow_before_outflow_is_not_a_transfer`; refine it to remain unpaired when
card-payment evidence is absent, and add the evidence-qualified repayment case
above as the failing PI-19 contract.

### PI-07: remedy the diagnosed layer

This is a **transfer detection/review UX plus history-coverage communication**
remedy, not an accounting or Sankey-category remedy.

- Extend candidate detection for depository-to-credit-card repayments to accept a
  small bounded reverse posting gap (the D/D+2 fixture) only when structural
  account roles and effective/provider payment evidence qualify the pair. Retain
  exact opposite amount, different accounts, known equal currency,
  active-duplicate exclusion, rejection memory, mutual unique-nearest matching,
  the generic reverse-order collision rejection, and explicit human confirmation.
  Consider the observed 4-day cases deliberately when choosing the bound; do not
  broaden it silently as part of the test fixture.
- Surface unresolved paired candidates as **counted until confirmed**, with a clear
  path to Transfer Detection. Confirmation must continue to exclude both sides
  through shared accounting everywhere; no category-name suppression is allowed.
- For an unpaired row with no covered counterpart, keep the conservative counted
  behavior and state that linked-account/history coverage cannot establish an
  internal transfer. Do not offer or imply one-click confirmation without a second
  covered row.
- If a confirmed pair ever contributes to aggregate or Activity spending, treat
  that as a shared-accounting regression and repair the shared predicate rather
  than the Sankey presentation.

## Verification

At commit `7c39934`, after the read-only investigation:

```text
.venv/bin/python -m pytest -q \
  tests/test_transfer_detector.py \
  tests/test_transfers_api.py \
  tests/test_cashflow_reporting.py \
  tests/test_analytics_contracts.py \
  tests/test_insights_analytics.py \
  tests/test_transaction_routes.py \
  tests/test_sankey_refund_credits.py

106 passed, 1 warning in 18.80s
```

The warning is Starlette's existing `httpx` TestClient deprecation warning. The
suite covers transfer validation/detection/confirmation, shared accounting,
Sankey payloads, and Activity transaction evidence.

```text
.venv/bin/python docs/roadmap/scan.py
Scanned 3 epics, 44 tasks; 0 issues.
```
