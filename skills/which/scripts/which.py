#!/usr/bin/env python3
import glob
import json
import math
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
import jev  # noqa: E402

CONFIG = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
USAGE_FILE = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home()) / ".claude.json"
NEVER_PICKED = {"ken:ken", "ponytail:ponytail", "i-have-adhd:i-have-adhd", "sensibility:which"}
REORDER_DEPTH = 6
READY_THRESHOLD = 0.5
DESCRIPTION_CHARS = 1536
CONTEXT_CHARS = 4000
WEAK_MATCH = "weak match: Jev found no clear fit, so this Pick leans on how often you use the skill."
TASK_QUESTION = (
    "The user typed the request in `prompt` and wants to prefix it with one skill. "
    "Which skill fits the request best? Each option is a skill name with what the skill does. "
    "Pick `none` when no skill in this list fits."
)

LENSES = {
    "higher": {
        "threshold": 0.7,
        "why": "The request is one step toward a bigger goal you would rather own.",
        "noul": {
            "type": "noul",
            "instructions": "The user typed the request in `prompt`. Is the request one step, such as fixing one bug, "
            "building one ticket, or making one document, that serves a bigger lasting goal the user would rather own?",
            "criteria": {
                "true": "The request is a single fix, ticket, or artifact, and a lasting outcome sits above it: "
                "an environment that keeps working, a product that stops losing users, a decision a meeting must take.",
                "false": "The request is already the lasting outcome, is creative work, is a quick question or a lookup, "
                "or is only a file path or an id with no words about the task. Also false when the request already "
                "states its purpose and the outcome beyond it.",
            },
        },
    },
    "deeper": {
        "threshold": 0.7,
        "why": "The request is loose, with no data to start from and no way to check the result.",
        "noul": {
            "type": "noul",
            "instructions": "The user typed the request in `prompt`. Does the request ask to build, fix, or decide "
            "something new and unclear, described in the user's own loose words, with no named data to start from "
            "and no way to check the result?",
            "criteria": {
                "true": "A loose description of a new build, a bug with an unknown cause, or an open design question, "
                "with no named logs, rows, or source to start from and no test or measurement to check the result.",
                "false": "A routine step such as review a PR, merge, rerun, or continue a ticket; a request that names "
                "its data, method, or test; a quick question; or only a file path, a URL, or an id.",
            },
        },
    },
    "wider": {
        "threshold": 0.7,
        "why": "Several kinds of people will judge the result, so methods from other fields help.",
        "noul": {
            "type": "noul",
            "instructions": "The user typed the request in `prompt`. Will people with different needs judge the "
            "result, so it would gain from the methods of several fields, such as design, finance, sales, writing, "
            "research, or hiring, and not only from engineering?",
            "criteria": {
                "true": "The request makes something several kinds of people will judge: a dashboard for several "
                "teams, a product feature with users and buyers, a hiring profile, a principle or policy, a story, a plan.",
                "false": "The request is a narrow step in one field: a bug fix, a code change, a query, a config edit, "
                "a command, a question about code, or a file path or an id with no words about the task.",
            },
        },
    },
    "prompt-master": {
        "threshold": 0.9,
        "why": "You asked for a prompt for another AI tool.",
        "noul": {
            "type": "noul",
            "instructions": "The user typed the request in `prompt`. Does the user ask for a prompt, that is, text to "
            "give to another AI tool or to a new AI session, or ask to improve a prompt?",
            "criteria": {
                "true": "The user asks for a prompt, a session prompt, instructions to paste into a new Claude Code "
                "session, or a better version of a prompt they wrote.",
                "false": "The user asks for the work itself, not for a prompt. A request that is itself a long prompt "
                "with instructions is false, unless it asks to rewrite or improve that prompt.",
            },
        },
    },
}
READY = {
    "type": "noul",
    "instructions": "Is `prompt` already a finished prompt for an AI agent: it states the goal and gives context, "
    "steps, constraints, or checks, often under headings or in numbered lists?",
    "criteria": {
        "true": "A worked prompt: a goal sentence plus context and explicit instructions, such as sections named "
        "Goal, Context, Steps, Objective, or Done when.",
        "false": "A loose request in the user's own words, a quick question, or only a file path, a URL, or an id.",
    },
}


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def files(root, pattern):
    return sorted(glob.glob(os.path.join(glob.escape(str(root)), pattern)))


def entries(value):
    value = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return [e for e in (v.strip().removeprefix("./").rstrip("/") for v in value if isinstance(v, str)) if e]


def plugin_roots():
    enabled = read_json(CONFIG / "settings.json").get("enabledPlugins", {})
    roots = {}
    for plugin, installs in read_json(CONFIG / "plugins/installed_plugins.json").get("plugins", {}).items():
        if installs:
            roots.setdefault(plugin, installs[0].get("installPath", ""))
    for synced in files(CONFIG / "plugins/synced", "*/"):
        stale = set(read_json(Path(synced) / "manifest.json").get("staleDirs", []))
        for manifest in files(synced, "*/.claude-plugin/plugin.json"):
            root = Path(manifest).parents[1]
            name = read_json(manifest).get("name")
            if name and root.name not in stale:
                roots.setdefault(f"{name}@synced", str(root))
    return {p: Path(r) for p, r in roots.items() if enabled.get(p) is not False and r and Path(r).is_dir()}


# shortcut: skillOverrides in settings is ignored; read it when a user sets one.
def sources(cwd):
    found = []

    def skills(root, prefix=""):
        found.extend((f, Path(f).parent.name, prefix, False) for f in files(root, "*/SKILL.md") if Path(f).parent.name != "synced")

    def commands(root, prefix=""):
        found.extend((f, os.path.relpath(f, root)[:-3].replace("/", ":"), prefix, True) for f in files(root, "*.md") + files(root, "*/*.md"))

    skills(CONFIG / "skills")
    commands(CONFIG / "commands")
    for synced in files(CONFIG / "skills/synced", "*/"):
        skills(synced, "anthropic-skills:")
    top = cwd
    while True:
        if top / ".claude" != CONFIG:
            skills(top / ".claude/skills")
            commands(top / ".claude/commands")
        if (top / ".git").exists() or top == top.parent:
            break
        top = top.parent
    if (top / ".git").is_file() and not (top / ".claude/skills").is_dir():
        gitdir = re.search(r"^gitdir: (.*)", (top / ".git").read_text(), re.M)
        if gitdir:
            skills(Path(gitdir.group(1).rsplit("/.git/worktrees/", 1)[0]) / ".claude/skills")
    for plugin, root in plugin_roots().items():
        prefix = plugin.rsplit("@", 1)[0] + ":"
        manifest = read_json(root / ".claude-plugin/plugin.json")
        skill_dirs = entries(manifest.get("skills"))
        skill_files = set(files(root, "skills/*/SKILL.md"))
        for e in skill_dirs:
            skill_files.update([str(root / e / "SKILL.md")] if (root / e / "SKILL.md").is_file() else files(root / e, "*/SKILL.md"))
        if not skill_dirs and not (root / "skills").is_dir() and (root / "SKILL.md").is_file():
            skill_files.add(str(root / "SKILL.md"))
        found.extend((f, Path(f).parent.name, prefix, False) for f in sorted(skill_files))
        # shortcut: an object-map "commands" falls back to commands/; read the map when a plugin uses one.
        for e in entries(manifest.get("commands")) or ["commands"]:
            if (root / e).is_file():
                found.append((str(root / e), Path(e).name.removesuffix(".md"), prefix, True))
            else:
                commands(root / e, prefix)
    return found


def frontmatter(path):
    try:
        lines = Path(path).read_text(errors="replace").split("\n")
    except OSError:
        return None, ""
    if not re.fullmatch(r"---[ \t]*", lines[0]):
        return None, ""
    fields, block, body = {}, None, ""
    for i, line in enumerate(lines[1:], 1):
        if re.fullmatch(r"---[ \t]*", line):
            body = next((rest for rest in lines[i + 1:] if rest.strip(" \t")), "")
            break
        key = re.match(r"([A-Za-z_-]+):[ \t]*(.*)", line)
        if key:
            name, value = key.groups()
            block = None
            if re.fullmatch(r"[>|][-+0-9]*[ \t]*", value):
                block, value = name, ""
            elif value[:1] in ('"', "'") and not re.search(value[0] + r"[ \t]*$", value[1:]):
                block = name
            fields[name] = value
        elif block and line.strip(" \t"):
            text = line.strip(" \t")
            fields[block] = f"{fields[block]} {text}" if fields[block] else text
    return fields, body


def unquote(text):
    return re.sub(r"^[\"']|[\"'][ \t]*$", "", text)


def skill(path, fallback, prefix, is_command):
    fields, body = frontmatter(path)
    if fields is None or re.match(r"[ \t]*false", fields.get("user-invocable", "")):
        return None
    name = unquote(fields.get("name", ""))
    if not name or is_command:
        name = fallback
    if name.startswith(prefix):
        name = name[len(prefix):]
    description = " ".join(filter(None, [unquote(fields.get("description", "")) or body, unquote(fields.get("when_to_use", ""))]))
    return {"name": prefix + name, "description": re.sub(r"[\t\r]", " ", description)[:DESCRIPTION_CHARS]}


def scan(cwd):
    roster, seen = [], set()
    for source in sources(cwd):
        found = skill(*source)
        if found and found["name"].lower() not in seen:
            seen.add(found["name"].lower())
            roster.append(found)
    return roster


def skill_question(skills):
    criteria = {s["name"]: s["description"] or None for s in skills}
    criteria["none"] = "No skill in this list fits the request."
    return {"type": "choice", "instructions": TASK_QUESTION, "criteria": criteria}


def questions(roster):
    tasks = sorted((s for s in roster if s["name"] not in LENSES and s["name"] not in NEVER_PICKED), key=lambda s: s["name"])
    qs = {f"h{i}": skill_question(half) for i, half in enumerate((tasks[0::2], tasks[1::2]))}
    lenses = sorted(LENSES.keys() & {s["name"] for s in roster})
    qs.update({name: LENSES[name]["noul"] for name in lenses})
    if lenses:
        qs["ready"] = READY
    return qs


def use_counts():
    usage = read_json(USAGE_FILE).get("skillUsage", {})
    return {name: entry.get("usageCount", 0) for name, entry in usage.items() if isinstance(entry, dict)}


def finalists(answers):
    fits = sorted(((p, name) for half in ("h0", "h1") for name, p in answers[half]["probabilities"].items()
                   if name != "none" and p >= answers[half]["probabilities"].get("none", 0)), reverse=True)
    return [name for _, name in fits[:REORDER_DEPTH]]


def ranked(answers, usage):
    if "final" in answers:
        probabilities = answers["final"]["probabilities"]
    else:
        fits = finalists(answers)
        probabilities = {name: p for half in ("h0", "h1") for name, p in answers[half]["probabilities"].items() if not fits or name in fits}
    candidates = sorted(((p, name) for name, p in probabilities.items() if name != "none"), reverse=True)
    return [name for _, name in sorted(((p * math.log2(usage.get(name, 0) + 2), name) for p, name in candidates[:REORDER_DEPTH]), reverse=True)]


def lens(answers):
    fired = [name for name, spec in LENSES.items() if name in answers and answers[name]["noul"] >= spec["threshold"]]
    if fired and answers["ready"]["noul"] < READY_THRESHOLD:
        return max(fired, key=lambda name: answers[name]["noul"])
    return None


def first_sentence(text):
    sentence = re.match(r".*?[.!?](?=\s|$)|.*", text).group(0).rstrip()
    return sentence + "." if sentence and sentence[-1] not in ".!?" else sentence


def pick(prompt, answers, roster, usage):
    order = ranked(answers, usage)
    chosen = lens(answers)
    if chosen:
        return [
            f"/{chosen} {prompt}",
            f"why: {LENSES[chosen]['why']}",
            f"next: Run /sensibility:which on the rewrite that /{chosen} gives you.",
            f"skip the Lens: /{order[0]} {prompt}",
        ]
    top = order[0]
    count = usage.get(top, 0)
    description = {s["name"]: s["description"] for s in roster}[top]
    lines = [f"/{top} {prompt}", " ".join(filter(None, ["why:", first_sentence(description), f"You ran it {count} time{'' if count == 1 else 's'}."]))]
    final = answers.get("final", {}).get("probabilities")
    lines += [f"runner-up: /{name}" for name in order[1:2] if not final or final[name] >= final.get("none", 0)]
    if all(answers[half]["choice"] == "none" for half in ("h0", "h1")):
        lines.append(WEAK_MATCH)
    return lines


def main():
    args, context = sys.argv[1:], ""
    if args[:1] == ["--context"] and len(args) > 1:
        context, args = args[1].strip()[:CONTEXT_CHARS], args[2:]
    prompt = " ".join(args).strip()
    try:
        if not prompt:
            raise jev.JevError("usage", "Type a prompt after /sensibility:which.", 1)
        roster = scan(Path.cwd())
        state = {"prompt": prompt, **({"context": context} if context else {})}
        answers = jev.ask(state, questions(roster))["answers"]
        fits = finalists(answers)
        if len(fits) > 1:
            answers["final"] = jev.ask(state, {"final": skill_question([s for s in roster if s["name"] in fits])})["answers"]["final"]
    except jev.JevError as e:
        jev.fail(e)
    print("\n".join(pick(prompt, answers, roster, use_counts())))


if __name__ == "__main__":
    main()
