# Sensibility

Sensibility lets Claude Code ask [Jev](https://docs.typesafe.ai), TypeSafe's judgment model, short typed questions while it works. Is this true? Which of these fits best? Where does this sit on these levels? Jev answers with probabilities in about half a second, at roughly $0.00005 per question batch. Jev doesn't write text. It only answers the questions it's given.

The plugin has four parts.

The judge skill, `/sensibility:judge`, is for Claude to use on its own: ranking options, checking a diff against its ticket, checking a commit message against its diff, or scoring how clearly a PR description reads. It ships with three reusable question sets, called batteries: `scope`, `commit` and `clarity`.

The battery skill, `/sensibility:battery`, turns a rule of yours into a new battery and tests it on examples before saving it. See [Batteries](#batteries).

The Risk gate is off by default. When it's on, it judges every Bash command before it runs. When a command is both risky and destructive, or risky and outside what you asked for, Claude Code stops and asks you:

```
Sensibility risk gate: risk 1.4/3, deletes or overwrites data, is outside what the user asked
```

Everything else runs as usual. With the gate on, each Bash call takes about 0.5 s longer. Force pushes, `DROP TABLE` and `rm -rf ~` get stopped, and a `git push` you asked for goes through.

The Finish gate is on by default. When Claude ends a turn short of what you asked (offering to do the work instead of doing it, asking permission you already gave, or stopping at a plan), Claude gets one nudge to keep going.

If there's no key, the network fails or Jev is slow, both gates let the command or reply through. They never block your work.

## Install

In Claude Code:

```
/plugin marketplace add rajnandan1/sensibility
/plugin install sensibility@sensibility
```

Or from a terminal:

```sh
claude plugin marketplace add rajnandan1/sensibility
claude plugin install sensibility@sensibility
```

From a local clone, run `claude plugin marketplace add /path/to/sensibility` and then the same `install` line. To try it for a single session without installing: `claude --plugin-dir /path/to/sensibility`.

You need `python3` on your PATH (3.9 or later, no packages). On macOS, `xcode-select --install` provides it. Tested on Claude Code 2.1.280.

## Set the key

1. Get a key at https://console.typesafe.ai/keys.
2. Export it in your shell, for example in `~/.zshenv`:

   ```sh
   export TYPESAFE_API_KEY=...
   ```

3. Restart Claude Code.

Without a key, the judge skill prints these steps and stops. The gates turn themselves off and show one message per session.

## Example: catch a change the ticket didn't ask for

The ticket says: *page 2 repeats the last item of page 1. Fix the slice. Nothing else is broken.* The diff fixes the slice, but it also changes `total_pages(count, size=20)` to `size=25`.

You ask Claude: *"Before I commit, use the sensibility judge to check my change against TICKET.md."*

```mermaid
sequenceDiagram
    participant You
    participant Claude
    participant J as judge.py
    participant Jev
    You->>Claude: check my change against TICKET.md
    Claude->>J: scope --state-file ticket=TICKET.md --git-diff HEAD
    J->>Jev: ticket + diff, 3 yes/no questions
    Jev-->>J: in_scope 0.05, complete 0.48, unrelated_change 0.93
    J-->>Claude: verdict: escalate
    Claude-->>You: Don't commit yet. Keep the slice fix, put size back to 20.
```

| Question | Answer | With `size=20` restored |
| --- | --- | --- |
| Is every change something the ticket asks for? | 0.05 | 0.97 |
| Does the diff do everything the ticket asks? | 0.48 | 0.96 |
| Is there an unrelated change? | 0.93 | 0.03 |
| Verdict | `escalate` | `act` |

The whole check took about half a second, and Claude never had to paste the diff into its own context. These numbers come from a real run; repeat runs moved them by a few hundredths and gave the same verdict every time.

## Turn the gates on or off

From a terminal (this works whether or not the plugin is already installed):

```sh
claude plugin install sensibility@sensibility --config bash_gate=true    # Risk gate on
claude plugin install sensibility@sensibility --config bash_gate=false   # Risk gate off
claude plugin install sensibility@sensibility --config stop_gate=false   # Finish gate off
```

Or in Claude Code, run `/plugin configure sensibility@sensibility`, type `true` or `false` in each field, and choose Save configuration.

`stop_gate` controls the Finish gate (default `true`) and `bash_gate` controls the Risk gate (default `false`). Restart Claude Code after you change them.

In testing on 51 real turns, the Finish gate fired 3 times and was right about once. Each wrong nudge costs one extra model turn. Turn it off if the nudges get in your way. Turn the Risk gate on if you want a second check before destructive shell commands.

## Batteries

A battery is a JSON file of questions for Jev, plus an optional gate that turns the answers into `act`, `confirm` or `escalate`. Five come built in (`scope`, `commit`, `clarity`, and the two gates' `finish` and `risk`). Your own go in `~/.claude/sensibility/batteries/` for every project, or `.claude/sensibility/batteries/` for one repo. Claude runs them by name, the same way as the built-ins.

The easiest way to make one is to describe the rule and let Claude build it:

```
/sensibility:battery make a battery called log-line: a log message must name the operation that failed and the record it failed on, and must never include passwords, API keys, or personal data like emails
```

In a test run, that prompt produced four yes/no questions (names the operation, names the record, leaks a secret, leaks personal data) and got all 16 test verdicts right. That included `password reset email send failed for user_id=...`, which mentions a password and an email without leaking either. The file is in [`examples/batteries/log-line.json`](examples/batteries/log-line.json).

The battery skill picks the question types, writes the file, runs it twice on at least six example cases it writes itself (or ones you give it), and adjusts the wording until every case gets the right verdict. Claude Code asks you once before it writes under `.claude/`.

### Example: comments that earn their place

The rule: a comment stays only if it explains something the code can't, such as a vendor quirk, a spec link or a lint suppression. Narration, history and "do not remove" notes go. That's a keep-list, so the battery asks one question: what kind of comment is this? ([`examples/batteries/comment.json`](examples/batteries/comment.json))

| Comment | Jev's answer | Verdict |
| --- | --- | --- |
| `# increment the retry counter` | narration | `escalate` |
| `# changed from 3 to 5 after the outage last week` | history | `escalate` |
| `# IMPORTANT: do not remove, this is fine for now` | justification | `escalate` |
| `# Safari drops Content-Length on 304 replies, so read the size from the cached copy` | outside_constraint | `act` |
| `# RFC 9110 section 15.4.5: a 304 response has no body` | spec_link | `act` |
| `// eslint-disable-next-line no-console` | suppression | `act` |

### Example: PR descriptions a newcomer can follow

The rule: plain prose, no template headers, no buzzwords, and it says what was broken and why the change fixes it. That's three independent checks, so the battery asks three yes/no questions. ([`examples/batteries/pr-description.json`](examples/batteries/pr-description.json))

| PR description | Template | Buzzwords | Explains why | Verdict |
| --- | --- | --- | --- | --- |
| `## Summary` / "introduces a robust enhancement" / `## Changes` / `## Testing` | 0.98 | 0.95 | 0.05 | `escalate` |
| "Updated jev.py to check the body of 403 responses. Added a blocked error." | 0.08 | 0.03 | 0.15 | `escalate` |
| "ok so the judge script treated every HTTP 403 as a missing key. Turns out the firewall also sends a 403 for some shell text…" | 0.04 | 0.03 | 0.89 | `act` |

All the scores above come from real runs. To use either example, copy the file into `~/.claude/sensibility/batteries/`.

The same goes for tuning a built-in: copy its file from [`batteries/`](batteries/) into one of your folders and edit the copy. A project copy wins over a user copy, and both win over the plugin's own. `risk` and `finish` load only from your user folder or the plugin, never from a project, so a repo you clone can't loosen your gates.

## What leaves your machine, and what gets logged

For each gate judgment, the plugin sends your last prompt plus the command or reply being judged to TypeSafe's API. If your prompts or commands must stay local, turn the gates off.

Each gate judgment is also appended to `judgments.jsonl` in the plugin's data directory under `~/.claude/plugins/data/`, with the state sent, the answers, the verdict and the latency. You can delete the file at any time. Judge skill calls are not logged.

## License

MIT. See [LICENSE](LICENSE).
