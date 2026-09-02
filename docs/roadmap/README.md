# Roadmap

Start with [_registry.md](_registry.md), then open the relevant epic and task. The
active priority is [trustworthy cashflow](epics/010-trustworthy-cashflow/_epic.md).
Read its [spirit](epics/010-trustworthy-cashflow/spirit.md) before choosing an
implementation. The [earlier feature backlog](../finance-intelligence-roadmap.md)
is preserved and deferred; it is not the current execution queue.

## Refresh and validate

From the repository root, using the project's Python environment:

```bash
python -m pip install -r docs/roadmap/requirements.txt
python docs/roadmap/scan.py
```

The scanner regenerates `_registry.md` and `_blocked.md` and exits nonzero on
invalid metadata or dependency/status issues. Run it at session start, after
task changes, and before committing roadmap changes. Never hand-edit its output.
It reads `_epic.md` and `tasks/*.md`; supporting prose such as `spirit.md` is not
a task. This is the only extra epic document requested for this roadmap.

## Coordination

- A `todo` task is ready only when every dependency is `done`. A null
  `assigned_agent` means unassigned; suggested roles live in the task body.
- Assign a task and set it `in-progress` when work actually starts. Do not mark
  dependencies done merely to unblock work. Record evidence and the commit tested
  before completion; append dated entries to the execution log.
- One coordinator owns changes to the registry and epic scope. Independent
  verification is performed by someone other than the implementer of that slice.
- For this setup, publish to `pr-22` as requested. Future parallel implementation
  should use isolated task branches/worktrees and coordinated integration.
- On a task pivot, retain the old file in place, mark it `superseded`, set
  `superseded_by` where applicable, and create a new ID. Never reuse IDs or delete
  history. Superseding an epic also requires a revision-log explanation.
- Material scope changes require an epic revision bump and a dated revision-log
  entry. Keep the spirit true to the user's intent rather than to a chosen design.
- `_archive/epics` and `_archive/tasks` are reserved for later archival. For now,
  keep superseded records in place so dependency references remain inspectable.

The first setup commit contains the structure and intent. The following commit
adds the task breakdown. Roadmap status does not imply that draft implementation
has been accepted, pushed, or deployed.
