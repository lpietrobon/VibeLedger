# Registry (generated — do not edit by hand)

_Last scan: 2026-09-11T05:25:09+00:00_

Read `_blocked.md` before selecting work. A todo task is ready only when all
dependencies are done; a blank assignment means unassigned.

## Epics

| id | title | status | rev | owner |
|---|---|---|---|---|
| [010-trustworthy-cashflow](epics/010-trustworthy-cashflow/_epic.md) | Trustworthy cashflow across linked accounts | done | 3 |  |
| [020-product-integrity](epics/020-product-integrity/_epic.md) | Product integrity and cleanup | planned | 2 |  |
| [030-inspectable-aggregates](epics/030-inspectable-aggregates/_epic.md) | Inspectable aggregates | planned | 1 |  |

## Tasks

| id | epic | status | deps | assigned | title |
|---|---|---|---|---|---|
| [CF-01](epics/010-trustworthy-cashflow/tasks/CF-01.md) | 010-trustworthy-cashflow | done |  | coordinator | Audit existing behavior and establish the baseline |
| [CF-02](epics/010-trustworthy-cashflow/tasks/CF-02.md) | 010-trustworthy-cashflow | done | CF-01 | coordinator | Define accounting expectations with worked examples |
| [CF-03](epics/010-trustworthy-cashflow/tasks/CF-03.md) | 010-trustworthy-cashflow | done | CF-01 |  | Review the spending and reconciliation experience |
| [CF-04](epics/010-trustworthy-cashflow/tasks/CF-04.md) | 010-trustworthy-cashflow | done | CF-01, CF-02 | coordinator | Establish focused regression fixtures and coverage checks |
| [CF-05](epics/010-trustworthy-cashflow/tasks/CF-05.md) | 010-trustworthy-cashflow | done | CF-02, CF-04 |  | Harden transaction identity and synchronization |
| [CF-06](epics/010-trustworthy-cashflow/tasks/CF-06.md) | 010-trustworthy-cashflow | done | CF-02, CF-04 |  | Make transfer reconciliation conservative and durable |
| [CF-07](epics/010-trustworthy-cashflow/tasks/CF-07.md) | 010-trustworthy-cashflow | done | CF-02, CF-04 |  | Unify posted cashflow totals and transaction evidence |
| [CF-08](epics/010-trustworthy-cashflow/tasks/CF-08.md) | 010-trustworthy-cashflow | done | CF-03, CF-07 |  | Make spending charts and drill-downs tell the same story |
| [CF-09](epics/010-trustworthy-cashflow/tasks/CF-09.md) | 010-trustworthy-cashflow | done | CF-03, CF-05, CF-06, CF-07 |  | Finish existing transaction review and recurring workflows |
| [CF-10](epics/010-trustworthy-cashflow/tasks/CF-10.md) | 010-trustworthy-cashflow | done | CF-05, CF-06, CF-07 |  | Independently verify accounting and reconciliation |
| [CF-11](epics/010-trustworthy-cashflow/tasks/CF-11.md) | 010-trustworthy-cashflow | done | CF-08, CF-09, CF-10, CF-14 |  | Independently verify the user-facing cashflow story |
| [CF-12](epics/010-trustworthy-cashflow/tasks/CF-12.md) | 010-trustworthy-cashflow | done | CF-10, CF-11 |  | Review maintainability and verify final test coverage |
| [CF-13](epics/010-trustworthy-cashflow/tasks/CF-13.md) | 010-trustworthy-cashflow | done | CF-12 |  | Prepare the verified handoff for user redeployment |
| [CF-14](epics/010-trustworthy-cashflow/tasks/CF-14.md) | 010-trustworthy-cashflow | done | CF-07, CF-08, CF-10 |  | Show net refund credits in cashflow allocation |
| [PI-01](epics/020-product-integrity/tasks/PI-01.md) | 020-product-integrity | done |  |  | Retire the legacy Streamlit application |
| [PI-02](epics/020-product-integrity/tasks/PI-02.md) | 020-product-integrity | done | PI-13 |  | Make category summary drilldowns consistent |
| [PI-03](epics/020-product-integrity/tasks/PI-03.md) | 020-product-integrity | done |  |  | Define the manual duplicate-correction contract |
| [PI-04](epics/020-product-integrity/tasks/PI-04.md) | 020-product-integrity | done | PI-03, PI-15 | pi04_duplicate_implementation | Implement durable duplicate relationships and accounting exclusion |
| [PI-05](epics/020-product-integrity/tasks/PI-05.md) | 020-product-integrity | done | PI-16, PI-17 |  | Add the duplicate correction and reversal workflow |
| [PI-06](epics/020-product-integrity/tasks/PI-06.md) | 020-product-integrity | done |  |  | Diagnose credit-card-payment contributions in Sankey |
| [PI-07](epics/020-product-integrity/tasks/PI-07.md) | 020-product-integrity | done | PI-06, PI-19 |  | Resolve the diagnosed card-payment Sankey gap |
| [PI-08](epics/020-product-integrity/tasks/PI-08.md) | 020-product-integrity | done | PI-21 |  | Improve Sankey label readability |
| [PI-09](epics/020-product-integrity/tasks/PI-09.md) | 020-product-integrity | done | PI-06 |  | Explore a simpler common-case Sankey composition |
| [PI-10](epics/020-product-integrity/tasks/PI-10.md) | 020-product-integrity | todo | PI-07, PI-08, PI-09, PI-23 |  | Implement the simpler Sankey composition |
| [PI-11](epics/020-product-integrity/tasks/PI-11.md) | 020-product-integrity | todo | PI-25 |  | Standardize ordinary textual date formatting |
| [PI-12](epics/020-product-integrity/tasks/PI-12.md) | 020-product-integrity | todo | PI-01, PI-14, PI-16, PI-18, PI-20, PI-22, PI-24, PI-26 |  | Independently verify the integrated product-integrity work |
| [PI-13](epics/020-product-integrity/tasks/PI-13.md) | 020-product-integrity | done |  |  | Pin category drilldown semantics with failing tests |
| [PI-14](epics/020-product-integrity/tasks/PI-14.md) | 020-product-integrity | done | PI-02 |  | Independently verify category drilldown TDD compliance |
| [PI-15](epics/020-product-integrity/tasks/PI-15.md) | 020-product-integrity | done | PI-03 |  | Pin duplicate-accounting and lifecycle behavior with failing tests |
| [PI-16](epics/020-product-integrity/tasks/PI-16.md) | 020-product-integrity | done | PI-04 |  | Independently verify duplicate accounting TDD compliance |
| [PI-17](epics/020-product-integrity/tasks/PI-17.md) | 020-product-integrity | done | PI-16 |  | Pin duplicate-correction interaction behavior with failing tests |
| [PI-18](epics/020-product-integrity/tasks/PI-18.md) | 020-product-integrity | done | PI-05 |  | Independently verify duplicate-correction UI TDD compliance |
| [PI-19](epics/020-product-integrity/tasks/PI-19.md) | 020-product-integrity | done | PI-06 |  | Pin the diagnosed card-payment Sankey regression with failing tests |
| [PI-20](epics/020-product-integrity/tasks/PI-20.md) | 020-product-integrity | done | PI-07 |  | Independently verify the card-payment Sankey correction |
| [PI-21](epics/020-product-integrity/tasks/PI-21.md) | 020-product-integrity | done |  |  | Pin Sankey readability and accessibility cases before visual changes |
| [PI-22](epics/020-product-integrity/tasks/PI-22.md) | 020-product-integrity | todo | PI-08 |  | Independently verify Sankey readability TDD compliance |
| [PI-23](epics/020-product-integrity/tasks/PI-23.md) | 020-product-integrity | todo | PI-07, PI-09, PI-22 |  | Pin the accepted Sankey composition with failing tests |
| [PI-24](epics/020-product-integrity/tasks/PI-24.md) | 020-product-integrity | todo | PI-10 |  | Independently verify Sankey composition TDD compliance |
| [PI-25](epics/020-product-integrity/tasks/PI-25.md) | 020-product-integrity | todo |  |  | Pin current-year-aware date formatting with failing tests |
| [PI-26](epics/020-product-integrity/tasks/PI-26.md) | 020-product-integrity | todo | PI-11 |  | Independently verify date-formatting TDD compliance |
| [INSP-01](epics/030-inspectable-aggregates/tasks/INSP-01.md) | 030-inspectable-aggregates | todo | PI-14 |  | Establish the shared spending-category drilldown contract |
| [INSP-02](epics/030-inspectable-aggregates/tasks/INSP-02.md) | 030-inspectable-aggregates | todo | INSP-01 |  | Drill from expanded Sankey categories into Activity |
| [INSP-03](epics/030-inspectable-aggregates/tasks/INSP-03.md) | 030-inspectable-aggregates | todo | INSP-01 |  | Drill from month-over-month movers into current-period Activity |
| [INSP-04](epics/030-inspectable-aggregates/tasks/INSP-04.md) | 030-inspectable-aggregates | todo | INSP-02, INSP-03 |  | Independently verify aggregate-to-Activity parity |
