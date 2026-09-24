---
name: judge
description: Ask Jev (TypeSafe's judgment model) for fast typed judgments during work - rank candidates, check a diff against its ticket, score quality, verify yes/no claims. Use when a decision can be phrased as yes/no, pick-one-of, or place-on-levels questions over some text.
---

# Judge

Jev answers typed questions about a **state** (text or JSON). It never generates text. One call takes ~0.5 s and costs a fraction of a cent, so use it freely.

## Run it

Always exactly this shape, as one Bash command and nothing else on the line:

```
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py '<questions JSON>' --state '<text or JSON>'
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py '<questions JSON>' --state-file path/under/cwd.txt
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py <battery> --state-file ticket=path/ticket.md --git-diff main...HEAD
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py <battery> --state '{"ticket":"text from the chat"}' --git-diff HEAD
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py --list
```

- Wrap JSON in single quotes. To put an apostrophe inside, write `'\''`.
- Never add `;`, `&&`, `|`, `>`, `<`, `$(...)`, backticks, `$VAR`, env prefixes, `cd`, or heredocs. Those make the command need permission.
- `--state-file key=path` (repeatable) builds an object state `{key: file text}`. Paths must be under the working directory. For long text not already in a file, write it with the Write tool first.
- `--git-diff <range>` runs `git diff <range>` itself and adds the output as state key `diff`. Combine it with `--state-file key=path`, or with `--state '{"ticket":"..."}'` when the other text came from the chat. Never redirect a diff to a file.
- Do not also `cat` or Read a file you pass with `--state-file`; the script reads it so your context stays clean.
- Budgets: about 32k tokens of state plus the longest question, 64k in total. Over budget the script refuses; filter the state to what the questions need, never truncate blindly.

Output is one JSON line: `{"answers":{...},"model":"jev-1.13.0","ms":412}`, plus `"verdict"` and `"rule"` when a battery has a gate.

## Errors

- Exit 2, `{"error":"key",...}`: relay `message` to the user verbatim and stop. Do not retry, do not look for keys.
- Exit 3, `{"error":"busy"}`: Jev is overloaded; already retried. Tell the user; do not loop.
- Exit 1, `{"error":"blocked"}`: TypeSafe's firewall rejected the state text. Paraphrase shell snippets (curl flags, system paths) and rerun once.
- Exit 1: bad input (`budget`, `state`, `usage`, `request` with the API's field path). Fix and rerun once.
- `python3: command not found`: tell the user to install python3 (`xcode-select --install` on macOS).

## Questions

`{"<id>": {"type": "...", "instructions": "...", "criteria": ...}}`. Ids are for you; Jev never sees them, so the whole question goes in `instructions`.

| Type | Use for | `criteria` | Answer |
| --- | --- | --- | --- |
| `noul` | is this true? | optional `{"true": "...", "false": "..."}` | `{"noul": 0.93}` probability of yes |
| `choice` | which one of these? | `{"option": "description or null", ...}`, max 255 | `choice`, `probabilities`, `confidence` |
| `score` | how much, on described levels? | array of 2 to 10 level descriptions, low to high | `score` (0-based, can fall between levels), `probabilities`, `confidence` |

Rules that make answers good:

1. One snap judgment per question, the kind an expert makes in a second. "Review this and decide" is not a question; split it.
2. Batch every independent question over the same state into one call. Answers run in parallel; ten questions cost about the same time as one.
3. Prefer object state with named fields and point at them in backticks: "Does `diff` touch `ticket.files`?"
4. Choice: add a `none` or `other` option whenever the list might not cover the case.
5. Score levels describe concrete situations, not "good/bad".
6. Send only what the question needs. Irrelevant state lowers accuracy.

Jev is weak at, so keep out of questions:

1. Intent: it reads the words literally. State the exact condition and put boundary cases in `criteria`.
2. Counting and arithmetic, including "more than N" and line counts. Count in code; ask one Noul per item and sum yourself.
3. Dates and times. Compare them yourself.
4. Indirection: double negatives, property-of-a-property. Name the field directly.
5. Irrelevant state. It lowers accuracy; filter first.

Reading answers: a Noul of 0.5 means "equally likely", not "medium". `confidence` is how peaked the probabilities are, not whether they are right. Do not compare numbers across types. Below ~0.5 confidence, treat a Choice as undecided.

## Built-in batteries

| Name | State keys | Answers | Gate |
| --- | --- | --- | --- |
| `scope` | `ticket`, `diff` | `in_scope`, `complete`, `unrelated_change` Nouls | act / confirm / escalate |
| `commit` | `message`, `diff` | `says_what`, `says_why`, `mismatch` Nouls | act / confirm / escalate |
| `clarity` | `text` | `actionable`, `ambiguity`, `padding` Scores, 0 to 3 | none (Taste) |

`finish` and `risk` are the hooks' batteries; you can run them too. `--list` shows every battery, including user ones in `.claude/sensibility/batteries/` and `~/.claude/sensibility/batteries/`.

Verdicts: `act` means go ahead; `confirm` means say what looks off and carry on unless it matters; `escalate` means stop and show the user the answers before acting. A verdict is advice from thresholds, not ground truth.

For ranking, test coverage, and anything without a battery, write the questions yourself. To save a rule as a new battery, follow the file format in [reference.md](reference.md), which also has more patterns, the full error table, and Jev's other weak spots.

## Example: rank candidates

```
${CLAUDE_PLUGIN_ROOT}/skills/judge/scripts/judge.py '{"best":{"type":"choice","instructions":"Which design in `designs` best fits `task`?","criteria":{"a":null,"b":null,"c":null,"none":"none of them fits"}},"a":{"type":"score","instructions":"How well does `designs.a` fit `task`?","criteria":["does not solve it","solves it with serious flaws","solves it with minor flaws","solves it cleanly"]}}' --state '{"task":"...","designs":{"a":"...","b":"...","c":"..."}}'
```
