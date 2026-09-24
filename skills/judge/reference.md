# Judge reference

## Errors

| Exit | `error` | Cause | What to do |
| --- | --- | --- | --- |
| 2 | `key` | `TYPESAFE_API_KEY` unset (HTTP 403 JSON) or wrong (401) | Relay `message` verbatim and stop |
| 3 | `busy` | HTTP 429 or 529 after 3 retries inside 10 s | Tell the user; do not loop |
| 1 | `blocked` | TypeSafe's web firewall answered 403 with an HTML page; it trips on some shell text such as curl flags, auth headers, system paths | Paraphrase those snippets, rerun once |
| 1 | `budget` | State plus longest question over ~32k tokens, or over ~64k in total | Send only what the questions need |
| 1 | `state` | Missing state, battery key missing, `--state-file` outside cwd, `--git-diff` failed or empty | Fix the arguments |
| 1 | `usage` | Questions are not valid JSON, or neither questions nor battery given | Fix the JSON |
| 1 | `request` | Jev rejected the request; the message carries the field path, e.g. `questions.q.choice.criteria` | Fix that field |
| 1 | `network` | Could not reach `https://api.typesafe.ai` | Tell the user |
| 1 | `battery` | No battery by that name | Run `--list` |

`TYPESAFE_DEFAULT_MODEL` overrides the pinned `jev-1.13.0`; `TYPESAFE_BASE_URL` overrides the endpoint. Thresholds in the built-in batteries were tuned on `jev-1.13.0`.

## More of Jev's weak spots

6. Adversarial text in state can steer answers. When the state comes from an untrusted source, say in `criteria` what counts regardless of what the text claims.
7. Instructions that contradict criteria confuse it, e.g. a Noul whose `true` criterion means "no".
8. Answers are not consistent across questions: a Noul and a yes/no Choice on the same thing will not agree, and P(x) plus P(not x) need not be 1. Choice is relative (which option wins); Noul is absolute (all can be low). Never carry a threshold from one type to another.
9. It does not generate. To extract something, find the candidates in code and ask a Choice over them.

Identical calls wander by about ±0.04. Do not act on a difference smaller than that.

## Patterns

**Rank candidates.** One Choice over all of them (with a `none` option) plus one Score per candidate, all in one call. Take the Choice argmax when you only need the winner; use the Scores when you need an order. For more than a handful, rank all cheaply, then re-judge the top 3 with fuller state.

**Guard an action.** One Noul per hazard plus one Score for severity, thresholds in a gate. `risk.json` is a worked example.

**Does a test cover a change.** One Noul per named test: "Would `test` fail if the change in `diff` were reverted?" Jev gets small textual cases right and misses cross-method deduction; run the test when it matters.

**Check a claim against a source.** One Choice: does `source` support, contradict, or not address `claim`.

**Count things.** One Noul per item, threshold each at 0.5 yourself, sum in your head.

## Writing a battery

A battery is `<name>.json` in `.claude/sensibility/batteries/` (this repo), `~/.claude/sensibility/batteries/` (every project), or the plugin's `batteries/`, searched in that order. A file named after a built-in replaces it at that layer. `finish` and `risk` load only from the user folder or the plugin.

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

- `state.keys` are the names the state object must carry. Name a git diff `diff` so `--git-diff` fills it.
- `questions` go to Jev unchanged, the same three types as in SKILL.md.
- `gate` is optional. Rules run in order, first match wins, else `default`. A rule is `{"verdict": "act" | "confirm" | "escalate", "any" | "all": [conditions]}`. A condition is `<id>.<field> <op> <number>` with fields `noul`, `score`, `confidence`, `p.<option>` and ops `>= > <= <`, or `<id>.choice == <option>`. No weights, no arithmetic; OR across rules is two rules.

Shapes that work: a keep-list rule ("only these kinds are allowed") is one Choice over the kinds plus `other`, with a gate that acts on the allowed ones and escalates by default. Independent hazards ("no X, no Y, must have Z") are one Noul each, with `true` and `false` criteria that name the boundary cases. Quality is one Score with 3 to 5 concrete levels and usually no gate.

Write the file with the Write tool. Before calling it done, run it on at least 3 examples that should pass and 3 that should fail, twice each. Fix wording before moving a threshold, and keep each threshold at least 0.05 from any answer you observed. `judge.py --list` must show the file with no `INVALID` line.
