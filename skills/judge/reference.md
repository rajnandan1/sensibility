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

The battery skill (`/sensibility:battery`) holds the file format and walks through writing and calibrating one.
