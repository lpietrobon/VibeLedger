# Registry (generated — do not edit by hand)

_Last scan: 2026-09-06T15:57:53+00:00_

Read `_blocked.md` before selecting work. A todo task is ready only when all
dependencies are done; a blank assignment means unassigned.

## Epics

| id | title | status | rev | owner |
|---|---|---|---|---|
| [010-trustworthy-cashflow](epics/010-trustworthy-cashflow/_epic.md) | Trustworthy cashflow across linked accounts | in-progress | 1 |  |

## Tasks

| id | epic | status | deps | assigned | title |
|---|---|---|---|---|---|
| [CF-01](epics/010-trustworthy-cashflow/tasks/CF-01.md) | 010-trustworthy-cashflow | done |  | coordinator | Audit existing behavior and establish the baseline |
| [CF-02](epics/010-trustworthy-cashflow/tasks/CF-02.md) | 010-trustworthy-cashflow | done | CF-01 | coordinator | Define accounting expectations with worked examples |
| [CF-03](epics/010-trustworthy-cashflow/tasks/CF-03.md) | 010-trustworthy-cashflow | blocked | CF-01 |  | Review the spending and reconciliation experience |
| [CF-04](epics/010-trustworthy-cashflow/tasks/CF-04.md) | 010-trustworthy-cashflow | done | CF-01, CF-02 | coordinator | Establish focused regression fixtures and coverage checks |
| [CF-05](epics/010-trustworthy-cashflow/tasks/CF-05.md) | 010-trustworthy-cashflow | done | CF-02, CF-04 |  | Harden transaction identity and synchronization |
| [CF-06](epics/010-trustworthy-cashflow/tasks/CF-06.md) | 010-trustworthy-cashflow | done | CF-02, CF-04 |  | Make transfer reconciliation conservative and durable |
| [CF-07](epics/010-trustworthy-cashflow/tasks/CF-07.md) | 010-trustworthy-cashflow | done | CF-02, CF-04 |  | Unify posted cashflow totals and transaction evidence |
| [CF-08](epics/010-trustworthy-cashflow/tasks/CF-08.md) | 010-trustworthy-cashflow | blocked | CF-03, CF-07 |  | Make spending charts and drill-downs tell the same story |
| [CF-09](epics/010-trustworthy-cashflow/tasks/CF-09.md) | 010-trustworthy-cashflow | blocked | CF-03, CF-05, CF-06, CF-07 |  | Finish existing transaction review and recurring workflows |
| [CF-10](epics/010-trustworthy-cashflow/tasks/CF-10.md) | 010-trustworthy-cashflow | blocked | CF-05, CF-06, CF-07 |  | Independently verify accounting and reconciliation |
| [CF-11](epics/010-trustworthy-cashflow/tasks/CF-11.md) | 010-trustworthy-cashflow | todo | CF-08, CF-09, CF-10 |  | Independently verify the user-facing cashflow story |
| [CF-12](epics/010-trustworthy-cashflow/tasks/CF-12.md) | 010-trustworthy-cashflow | blocked | CF-10, CF-11 |  | Review maintainability and verify final test coverage |
| [CF-13](epics/010-trustworthy-cashflow/tasks/CF-13.md) | 010-trustworthy-cashflow | blocked | CF-12 |  | Prepare the verified handoff for user redeployment |
