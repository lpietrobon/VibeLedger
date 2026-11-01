#!/usr/bin/env python3
"""Validate roadmap metadata and regenerate its two indexes. No application imports."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import frontmatter

ROOT = Path(__file__).resolve().parent
EPIC_STATUSES = {"planned", "scoping", "in-progress", "blocked", "done", "superseded"}
TASK_STATUSES = {"todo", "in-progress", "blocked", "done", "superseded"}


def load_records(root, pattern, required, statuses, issues):
    records = []
    for path in sorted(root.glob(pattern)):
        name = path.relative_to(root).as_posix()
        try:
            data = dict(frontmatter.load(path).metadata)
            missing = required - data.keys()
            if missing:
                raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
            if not isinstance(data["id"], str) or not data["id"].strip():
                raise ValueError("id must be a nonempty string")
            if not isinstance(data["title"], str) or not data["title"].strip():
                raise ValueError("title must be a nonempty string")
            if not isinstance(data["status"], str) or data["status"] not in statuses:
                raise ValueError("invalid status")
            if path.name == "_epic.md":
                if path.parent.name != data["id"]:
                    raise ValueError("epic id must match its folder")
                if type(data["revision"]) is not int or data["revision"] < 1:
                    raise ValueError("revision must be a positive integer")
            else:
                if path.stem != data["id"]:
                    raise ValueError("task id must match its filename")
                if path.parent.parent.name != data["epic"]:
                    raise ValueError("epic must match the containing epic folder")
                deps = data["dependencies"]
                if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
                    raise ValueError("dependencies must be a list of task IDs")
                if data["superseded_by"] is not None:
                    if not isinstance(data["superseded_by"], str):
                        raise ValueError("superseded_by must be a task ID or null")
                    if data["status"] != "superseded":
                        raise ValueError("only superseded tasks can have superseded_by")
            records.append({**data, "file": name})
        except Exception as exc:
            issues.append(f"{name}: {exc}")
    return records


def validate(epics, tasks, issues):
    seen = set()
    for record in epics + tasks:
        if record["id"] in seen:
            issues.append(f"Duplicate ID: {record['id']}")
        seen.add(record["id"])
    epic_ids = {e["id"] for e in epics}
    by_id = {t["id"]: t for t in tasks}
    for task in tasks:
        ident = task["id"]
        if task["epic"] not in epic_ids:
            issues.append(f"{ident}: unknown epic {task['epic']}")
        replacement = task["superseded_by"]
        if replacement and (replacement not in by_id or replacement == ident):
            issues.append(f"{ident}: invalid replacement {replacement}")
        for dep in task["dependencies"]:
            other = by_id.get(dep)
            if other is None:
                issues.append(f"{ident}: depends on unknown task {dep}")
            elif other["status"] == "superseded":
                issues.append(f"{ident}: depends on superseded task {dep} "
                              f"(-> {other['superseded_by'] or 'nothing'})")
            elif task["status"] in {"in-progress", "done"} and other["status"] != "done":
                issues.append(f"{ident}: marked {task['status']} but dependency {dep} is not done")

    visiting, visited = set(), set()

    def visit(ident, chain):
        if ident in visiting:
            issues.append(f"Cycle: {' -> '.join(chain + [ident])}")
            return
        if ident in visited or ident not in by_id:
            return
        visiting.add(ident)
        for dep in by_id[ident]["dependencies"]:
            visit(dep, chain + [ident])
        visiting.remove(ident)
        visited.add(ident)

    for ident in by_id:
        visit(ident, [])


def cell(value):
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return ["| " + " | ".join(headers) + " |",
            "|" + "|".join("---" for _ in headers) + "|"] + [
        "| " + " | ".join(cell(v) for v in row) + " |" for row in rows
    ]


def scan(root=ROOT):
    issues = []
    epics = load_records(root, "epics/*/_epic.md",
                         {"id", "title", "status", "created", "revision"}, EPIC_STATUSES, issues)
    tasks = load_records(root, "epics/*/tasks/*.md",
                         {"id", "epic", "title", "status", "dependencies", "superseded_by",
                          "assigned_agent", "created"}, TASK_STATUSES, issues)
    validate(epics, tasks, issues)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = ["# Registry (generated — do not edit by hand)", "", f"_Last scan: {stamp}_", "",
             "Read `_blocked.md` before selecting work. A todo task is ready only when all",
             "dependencies are done; a blank assignment means unassigned.", "", "## Epics", ""]
    lines += table(["id", "title", "status", "rev", "owner"], [
        [f"[{e['id']}]({e['file']})", e["title"], e["status"], e["revision"], e.get("owner")]
        for e in epics])
    lines += ["", "## Tasks", ""]
    lines += table(["id", "epic", "status", "deps", "assigned", "title"], [
        [f"[{t['id']}]({t['file']})", t["epic"], t["status"],
         ", ".join(t["dependencies"]), t["assigned_agent"], t["title"]] for t in tasks])
    (root / "_registry.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    blocked = ["# Blocked / Issues (generated — do not edit by hand)", "", f"_Last scan: {stamp}_", ""]
    blocked += [f"- {issue}" for issue in issues] or ["None."]
    blocked += ["", "Tasks with unfinished dependencies may remain todo; that alone is not an issue."]
    (root / "_blocked.md").write_text("\n".join(blocked) + "\n", encoding="utf-8")
    print(f"Scanned {len(epics)} epics, {len(tasks)} tasks; {len(issues)} issues.")
    return bool(issues)


if __name__ == "__main__":
    sys.exit(scan())
