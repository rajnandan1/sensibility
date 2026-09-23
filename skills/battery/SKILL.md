---
name: battery
description: Create or edit a Sensibility battery - turn a rule, style guide, or checklist into reusable Jev questions with a gate that the judge skill runs by name. Use when the user wants a rule checked the same way every time.
---

# Battery

A battery is a JSON file of Jev questions plus an optional gate; the judge skill runs it by name. Everything needed to write one is in this file.

Tools, so the run needs as few permission prompts as possible:

- Write the battery with the Write tool. Claude Code asks the user once before writing under `.claude/`; that approval is expected.
- Run each judge call as its own Bash command, exactly this shape and nothing else on the line. The plugin approves this shape automatically; loops, `cd`, heredocs, `;` or pipes turn it into a command the user has to approve.

```
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py <name> --state '<JSON>'
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py --list
```

Independent judge calls can go out in parallel in one message.

## File format

`<name>.json`, looked up by filename: project `.claude/sensibility/batteries/` first, then user `~/.claude/sensibility/batteries/`, then the plugin's built-ins. A file with a built-in's name replaces it at that layer. `finish` and `risk` load only from the user folder or the plugin.

```json
{
  "description": "One line shown by --list",
  "state": { "description": "`comment`: the comment text. `code`: the lines it sits above.", "keys": ["comment", "code"] },
  "questions": {
    "kind": {
      "type": "choice",
      "instructions": "What kind of comment is `comment`, given the `code` it sits above?",
      "criteria": {
        "outside_constraint": "Explains behaviour forced by something outside this codebase: a vendor bug, a platform quirk, a protocol.",
        "spec_link": "Links an issue, RFC, or spec that carries a constraint.",
        "narration": "Restates what the code does.",
        "history": "Describes past changes, who changed it, or when.",
        "other": "None of the above."
      }
    }
  },
  "gate": {
    "rules": [
      { "verdict": "act", "any": ["kind.choice == outside_constraint", "kind.choice == spec_link"] },
      { "verdict": "confirm", "any": ["kind.choice == other", "kind.confidence < 0.5"] }
    ],
    "default": "escalate"
  }
}
```

- `questions` go to Jev unchanged. `noul`: optional `criteria` `{"true": "...", "false": "..."}`, answer `noul` 0 to 1. `choice`: `criteria` maps each option to a description or null, max 255, answer `choice`, `probabilities`, `confidence`. `score`: `criteria` is an array of 2 to 10 level descriptions, low to high, answer `score` (can fall between levels), `probabilities`, `confidence`.
- `gate` is optional. Rules run in order, first match wins, else `default`. Each rule is `{"verdict": "act" | "confirm" | "escalate", "any" | "all": [conditions]}`. A condition is `<id>.<field> <op> <number>` with fields `noul`, `score`, `confidence`, `p.<option>` and ops `>= > <= <`, or `<id>.choice == <option>`. No weights, no arithmetic; OR across rules is two rules.
- Verdicts: `act` means go ahead, `confirm` means flag it and carry on, `escalate` means stop and show the user.

## 1. Pin down the rule

Collect from the user, or from the file or doc they point at:

- **The rule** in their own words.
- **The state**: what text gets judged, split into named keys (`comment` and `code`, `message` and `diff`). Each key becomes a `state.keys` entry.
- **Labelled examples**: at least 3 that should pass and 3 that should fail, drawn from real code or text where possible, each with the verdict it should get. When the user gives none, write them yourself from the rule and show them in the report.
- **Where it lives**: `~/.claude/sensibility/batteries/` for every project (the default), or `.claude/sensibility/batteries/` for this repo only.
- **A name**: short kebab-case. `finish` and `risk` load only from the user folder; reusing a built-in name replaces it at that layer.

Done when every item above has a concrete value.

## 2. Write the questions

Pick the shape from the rule:

- **Keep-list** ("only these kinds are allowed"): one Choice over the kinds, allowed and banned, plus `other`. The gate acts on the allowed choices and escalates by default. This is the most reliable shape: the comment battery above, with a few more kinds, scored 12 of 12 with confidence 0.97 or more.
- **Independent hazards** ("no X, no Y, must have Z"): one Noul per hazard, each with `true` and `false` criteria that name the boundary cases.
- **Quality on a scale**: a Score with 3 to 5 levels that each describe a concrete situation. Usually no gate; that makes it a Taste battery.

Every question is one snap judgment about named state keys, written in `instructions` (Jev never sees the id). Counting, lengths, dates, and arithmetic stay out of the questions; check those in code or yourself.

Write the file with the Write tool. Done when `judge.py --list` shows the battery with its layer and no `INVALID` line.

## 3. Calibrate

Run the battery on every labelled example, twice each, and tabulate expected verdict, actual verdict, and the answers.

When an example lands wrong, fix the wording first: sharpen `instructions` or `criteria`, or switch to a Choice. Move a threshold only after the wording is right, and place it in the gap between the pass and fail answers you observed, at least 0.05 from any of them (Jev wanders about ±0.04 between identical calls).

Done when every labelled example gets its expected verdict on both runs.

## 4. Report

Give the user the file path, the calibration table, and one command that runs the battery on their own text.
