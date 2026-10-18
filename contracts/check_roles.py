#!/usr/bin/env python3
"""Check that ROLES.md and the role definitions in .claude/agents/ agree.

Checks:
  - every definition has a name and description, and its name matches its file name
  - every definition is listed in ROLES.md with the same status
  - every role marked building or active in ROLES.md has a definition
  - can_call only names roles that have a definition (and not the role itself);
    a role that can call others has the Agent tool when it restricts tools
  - every preloaded skill exists in .claude/skills/<skill>/SKILL.md
  - status, runs_on and autonomy_max use allowed values
Warns (does not fail) when a definition is over 100 lines.

Usage: python3 contracts/check_roles.py
Exit code: 0 ok, 1 at least one error.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROLES = REPO / "ROLES.md"
AGENTS = REPO / ".claude" / "agents"
SKILLS = REPO / ".claude" / "skills"

STATUSES = {"planned", "building", "active", "paused", "retired"}
RUNS_ON = {"cloud", "server", "local-device", "caller"}
AUTONOMY = {f"R{i}" for i in range(7)}
MAX_LINES = 100


def strip_comment(value):
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def parse_scalar(value):
    value = strip_comment(value)
    if value.startswith("[") and value.endswith("]"):
        return [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
    return value.strip("'\"")


def frontmatter(text):
    """Minimal parser for the flat YAML header used in role definitions."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    data, key = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and key is not None:
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(parse_scalar(item.group(1)))
            continue
        pair = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if pair:
            key, value = pair.group(1), pair.group(2)
            data[key] = parse_scalar(value) if value.strip() else ""
        elif key is not None and line.startswith((" ", "\t")) and isinstance(data[key], str):
            data[key] = (data[key] + " " + strip_comment(line)).strip()
    return data


def as_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def roles_from_plan(errors):
    roles, current = {}, None
    for n, line in enumerate(ROLES.read_text(encoding="utf-8").splitlines(), 1):
        heading = re.match(r"^###\s+([a-z0-9-]+)\s*$", line)
        if heading:
            current = heading.group(1)
            if current in roles:
                errors.append(f"ROLES.md:{n}: role '{current}' is listed twice")
            roles[current] = None
            continue
        status = re.match(r"^-\s+\*\*Status:\*\*\s+([a-z-]+)", line)
        if status and current and roles[current] is None:
            roles[current] = status.group(1)
            if status.group(1) not in STATUSES:
                errors.append(f"ROLES.md:{n}: '{current}' has unknown status '{status.group(1)}'")
        row = re.match(r"^\|\s*\d+\s*\|\s*\[([a-z0-9-]+)\]\([^)]*\)\s*\|\s*([a-z-]+)\s*\|", line)
        if row:
            roles.setdefault(("table", row.group(1)), row.group(2))
    table = {k[1]: v for k, v in roles.items() if isinstance(k, tuple)}
    roles = {k: v for k, v in roles.items() if not isinstance(k, tuple)}
    for rid, status in roles.items():
        if status is None:
            errors.append(f"ROLES.md: '{rid}' has no '- **Status:**' line")
        if rid not in table:
            errors.append(f"ROLES.md: '{rid}' is missing from the summary table")
        elif status and table[rid] != status:
            errors.append(f"ROLES.md: '{rid}' is '{table[rid]}' in the table but '{status}' in its entry")
    for rid in table:
        if rid not in roles:
            errors.append(f"ROLES.md: '{rid}' is in the table but has no '### {rid}' entry")
    return roles


def main():
    errors, warnings = [], []
    roles = roles_from_plan(errors)
    defs = {}
    for path in sorted(AGENTS.glob("*.md")):
        rel = path.relative_to(REPO)
        text = path.read_text(encoding="utf-8")
        data = frontmatter(text)
        if data is None:
            errors.append(f"{rel}: no YAML header between '---' lines")
            continue
        for field in ("name", "description"):
            if not data.get(field):
                errors.append(f"{rel}: missing '{field}'")
        if data.get("name") and data["name"] != path.stem:
            errors.append(f"{rel}: name '{data['name']}' does not match the file name")
        defs[path.stem] = (rel, data)
        if len(text.splitlines()) > MAX_LINES:
            warnings.append(f"{rel}: {len(text.splitlines())} lines; keep definitions under about {MAX_LINES}")

    for rid, (rel, data) in defs.items():
        status = data.get("status")
        if status not in STATUSES:
            errors.append(f"{rel}: status '{status}' is not one of {sorted(STATUSES)}")
        if rid not in roles:
            errors.append(f"{rel}: role '{rid}' is not listed in ROLES.md")
        elif roles[rid] and status and roles[rid] != status:
            errors.append(f"{rel}: status '{status}' but ROLES.md says '{roles[rid]}'")
        if data.get("runs_on") not in RUNS_ON:
            errors.append(f"{rel}: runs_on '{data.get('runs_on')}' is not one of {sorted(RUNS_ON)}")
        if data.get("autonomy_max") not in AUTONOMY:
            errors.append(f"{rel}: autonomy_max '{data.get('autonomy_max')}' is not R0 to R6")
        can_call = as_list(data.get("can_call"))
        for target in can_call:
            if target == rid:
                errors.append(f"{rel}: can_call lists the role itself")
            elif target not in defs:
                errors.append(f"{rel}: can_call names '{target}', which has no definition in .claude/agents/")
        tools = as_list(data.get("tools"))
        if can_call and tools and "Agent" not in tools:
            errors.append(f"{rel}: can_call is not empty but tools does not include Agent")
        for skill in as_list(data.get("skills")):
            if not (SKILLS / skill / "SKILL.md").is_file():
                errors.append(f"{rel}: skill '{skill}' not found at .claude/skills/{skill}/SKILL.md")

    for rid, status in roles.items():
        if status in ("building", "active") and rid not in defs:
            errors.append(f"ROLES.md: '{rid}' is {status} but has no .claude/agents/{rid}.md")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    built = sum(1 for s in roles.values() if s in ("building", "active"))
    print(f"{len(roles)} roles in ROLES.md, {len(defs)} definitions, {built} building or active: "
          f"{'ok' if not errors else f'{len(errors)} error(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
