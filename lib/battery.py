import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK_ONLY = {"finish", "risk"}
CONDITION = re.compile(r"^(\w+)\.(noul|score|confidence|choice|p\.\S+) (>=|>|<=|<|==) (\S+)$")


def layers():
    return [
        ("project", Path.cwd() / ".claude/sensibility/batteries"),
        ("user", Path.home() / ".claude/sensibility/batteries"),
        ("plugin", PLUGIN_ROOT / "batteries"),
    ]


def find(name):
    for layer, directory in layers():
        path = directory / f"{name}.json"
        if path.is_file() and not (layer == "project" and name in HOOK_ONLY):
            return layer, path
    return None


def validate(battery):
    for key in ("description", "state", "questions"):
        if key not in battery:
            raise ValueError(f"missing `{key}`")
    for rule in battery.get("gate", {}).get("rules", []):
        for cond in rule.get("any", []) + rule.get("all", []):
            m = CONDITION.match(cond)
            if not m or m.group(1) not in battery["questions"]:
                raise ValueError(f"bad condition `{cond}`")


def list_all():
    seen = {}
    for layer, directory in layers():
        for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            name = path.stem
            if layer == "project" and name in HOOK_ONLY:
                print(f"{name}\tIGNORED {path} (hook batteries load from user or plugin only)")
                continue
            try:
                battery = json.loads(path.read_text())
                validate(battery)
            except (ValueError, json.JSONDecodeError) as e:
                print(f"{name}\tINVALID {path}: {e}")
                sys.exit(1)
            if name in seen:
                print(f"{name}\tshadowed by {seen[name]} ({path})")
            else:
                seen[name] = layer
                print(f"{name}\t{layer}\t{battery['description']}")


def field(answer, name):
    if name.startswith("p."):
        return answer.get("probabilities", {}).get(name[2:], 0.0)
    return answer.get(name)


def holds(cond, answers):
    qid, name, op, rhs = CONDITION.match(cond).groups()
    if qid not in answers:
        return False
    value = field(answers[qid], name)
    if op == "==":
        return value == rhs
    rhs = float(rhs)
    return {">=": value >= rhs, ">": value > rhs, "<=": value <= rhs, "<": value < rhs}[op]


def gate(spec, answers):
    for rule in spec["rules"]:
        if ("any" in rule and any(holds(c, answers) for c in rule["any"])) or (
            "all" in rule and all(holds(c, answers) for c in rule["all"])
        ):
            return rule["verdict"], " and ".join(rule.get("all", [])) or " or ".join(rule["any"])
    return spec["default"], "default"
