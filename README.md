# Sensibility

Sensibility gives Claude Code a second opinion it can ask for in half a second.

Claude makes lots of small calls while it works: does this diff match the ticket, is this commit message honest, is this shell command safe to run, did I actually finish what was asked. Sensibility lets Claude hand those calls to [Jev](https://docs.typesafe.ai), a model from TypeSafe that only answers questions. Jev doesn't write code or text. You give it some text and a few questions, and it returns a probability for each answer in about 0.5 s, for about $0.00005.

## Quick start

**1. Install the plugin.** In Claude Code:

```
/plugin marketplace add rajnandan1/sensibility
/plugin install sensibility@sensibility
```

**2. Add your TypeSafe key.** Get one at https://console.typesafe.ai/keys, then add this line to `~/.zshenv` (or your shell's startup file):

```sh
export TYPESAFE_API_KEY=your-key-here
```

**3. Restart Claude Code** so it picks up the key and the plugin.

**4. Try it.** In any git repo with uncommitted changes, paste this with your own ticket text:

```
Use the sensibility judge to check my uncommitted change against this ticket: <paste the ticket>
```

Claude runs one command and reports a verdict (`act`, `confirm` or `escalate`) with the numbers behind it. If something is off, it tells you what.

You also need `python3` 3.9 or later on your PATH. macOS has it after `xcode-select --install`. Tested on Claude Code 2.1.280.

## How it works

You only need four words:

- **Jev**: TypeSafe's judging model. It answers questions about some text. It never writes anything.
- **Question**: one thing you ask Jev. There are three kinds. A yes/no question returns the chance the answer is yes (0.93 means very likely). A pick-one question chooses from options you list. A score question places the text on levels you describe.
- **Battery**: a saved set of questions in a JSON file, reused by name. `scope`, for example, asks three questions about a diff and a ticket.
- **Gate**: rules inside a battery that turn Jev's answers into one verdict: `act` (go ahead), `confirm` (flag it, carry on) or `escalate` (stop and show you).

Sensibility uses them in two ways:

```mermaid
flowchart LR
    subgraph ask ["When Claude asks"]
        A[You or Claude] --> B["judge skill<br/>(/sensibility:judge)"]
    end
    subgraph auto ["Automatically"]
        C["Bash command about to run"] --> D[Risk gate hook]
        E["Claude ends its turn"] --> F[Finish gate hook]
    end
    B --> G[a battery, or questions written on the spot]
    D --> H[risk battery]
    F --> I[finish battery]
    G --> J((Jev))
    H --> J
    I --> J
    J --> K["answers + verdict"]
```

**The judge skill** runs when you or Claude ask for it. It can use any battery, or questions Claude writes on the spot.

**The two gates** are hooks. They run on their own, each with its own battery:

| Gate | Runs when | What it does | Default |
| --- | --- | --- | --- |
| Finish gate | Claude ends a turn | If Claude stopped short (offered to do the work instead of doing it, asked permission you already gave, ended on a plan), Claude gets one nudge to keep going. | **on** |
| Risk gate | Before every Bash command | If a command is risky and destructive, or risky and outside what you asked for, Claude Code stops and asks you first. | **off** |

**The battery skill** (`/sensibility:battery`) turns a rule of yours into a new battery and tests it before saving.

## Things to ask Claude

| You want to | Say something like | What runs |
| --- | --- | --- |
| Check a change against its ticket | "Use the sensibility judge to check my uncommitted change against TICKET.md" | `scope` battery |
| Check a commit message | "Use the sensibility judge to check my last commit message against its diff" | `commit` battery |
| Rate a PR or issue description | "Use the sensibility judge to score how clear this PR description is: ..." | `clarity` battery |
| Pick between options | "Use the sensibility judge to pick which of these three approaches best fits the ticket" | questions Claude writes on the spot |
| Save a rule as a check | "/sensibility:battery make a battery called log-line: a log message must name the operation that failed and the record it failed on, and must never include passwords, API keys, or personal data like emails" | the battery skill |
| See every battery | "List the sensibility batteries" | `judge.py --list` |

### Example: catching a change the ticket didn't ask for

The ticket says: *page 2 repeats the last item of page 1. Fix the slice. Nothing else is broken.* The diff fixes the slice, but it also changes `total_pages(count, size=20)` to `size=25`.

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

The script read the ticket and ran `git diff` itself, so Claude got the verdict without loading the diff first. The numbers come from a real run; repeat runs moved them by a few hundredths and always gave the same verdict.

## Your own batteries

A battery is one JSON file. Five come with the plugin: `scope`, `commit` and `clarity` for the judge skill, and `risk` and `finish` for the two gates. Yours go in one of two folders:

- `~/.claude/sensibility/batteries/` works in every project.
- `.claude/sensibility/batteries/` inside a repo works in that repo only.

**Making one.** Describe the rule to the battery skill:

```
/sensibility:battery make a battery called log-line: a log message must name the operation that failed and the record it failed on, and must never include passwords, API keys, or personal data like emails
```

It chooses the question types, writes the file, and runs it twice on at least six example cases (its own, or yours). If a case gets the wrong verdict, it rewrites the questions and tries again. When every case comes out right, it shows you the results. Claude Code asks you once before it writes into `.claude/`.

For the prompt above, a test run produced four yes/no questions (names the operation, names the record, leaks a secret, leaks personal data) and got all 16 test verdicts right. That included `password reset email send failed for user_id=...`, which mentions a password and an email without leaking either.

**Using one.** Claude runs a battery when you name it ("check this with `log-line`"). For a check that should happen every time, add a line to your `CLAUDE.md`, such as *"Before you commit, run the `commit` and `log-line` batteries."*

**Changing a built-in.** Copy its file from [`batteries/`](batteries/) into one of your folders and edit the copy. A project copy wins over a user copy, and both win over the plugin's.

### Three example batteries

Copy any of these into `~/.claude/sensibility/batteries/` to use them.

**[`comment.json`](examples/batteries/comment.json)** keeps a code comment only if it explains something the code can't. It asks one pick-one question: what kind of comment is this?

| Comment | Jev's pick | Verdict |
| --- | --- | --- |
| `# increment the retry counter` | narration | `escalate` |
| `# changed from 3 to 5 after the outage last week` | history | `escalate` |
| `# IMPORTANT: do not remove, this is fine for now` | justification | `escalate` |
| `# Safari drops Content-Length on 304 replies, so read the size from the cached copy` | outside_constraint | `act` |
| `# RFC 9110 section 15.4.5: a 304 response has no body` | spec_link | `act` |
| `// eslint-disable-next-line no-console` | suppression | `act` |

**[`pr-description.json`](examples/batteries/pr-description.json)** wants plain prose that says what was broken and why the change fixes it. It asks three yes/no questions.

| PR description | Template headers | Buzzwords | Explains why | Verdict |
| --- | --- | --- | --- | --- |
| `## Summary` / "introduces a robust enhancement" / `## Changes` / `## Testing` | 0.98 | 0.95 | 0.05 | `escalate` |
| "Updated jev.py to check the body of 403 responses. Added a blocked error." | 0.08 | 0.03 | 0.15 | `escalate` |
| "ok so the judge script treated every HTTP 403 as a missing key. Turns out the firewall also sends a 403 for some shell text…" | 0.04 | 0.03 | 0.89 | `act` |

**[`log-line.json`](examples/batteries/log-line.json)** is the battery built by the prompt above.

All scores in these tables come from real runs.

## Turn the gates on or off

From a terminal:

```sh
claude plugin install sensibility@sensibility --config bash_gate=true    # Risk gate on
claude plugin install sensibility@sensibility --config stop_gate=false   # Finish gate off
```

Use `=true` or `=false` with either name. The command works even when the plugin is already installed. Run `/reload-plugins` or restart Claude Code afterwards.

You can also run `/plugin configure sensibility@sensibility` inside Claude Code, type `true` or `false` in each field, and choose Save configuration.

## FAQ

**How do I see my current settings?**
Look for `sensibility@sensibility` under `pluginConfigs` in `~/.claude/settings.json`. If it isn't there, you're on the defaults: Finish gate on, Risk gate off. `claude plugin details sensibility@sensibility` lists what the plugin installs.

**Do the gates use batteries?**
Yes. The Risk gate uses the `risk` battery and the Finish gate uses `finish`. To change what a gate asks or when it steps in, copy its battery into `~/.claude/sensibility/batteries/` and edit it. Gate batteries never load from a project folder, so a repo you clone can't loosen your gates.

**If batteries decide what a gate does, why are there on/off options?**
A battery decides how a gate judges. The option decides whether it runs at all. When a gate is off, its hook exits straight away: no call to Jev, no delay, nothing sent to TypeSafe. A battery that always says `act` would still call Jev on every event.

**I made a battery. Does it need a hook?**
No. The judge skill runs any battery by name. Claude doesn't know yours exists until you mention it or it runs `--list`, so name it in your request or add it to your `CLAUDE.md`. Write your own hook only when the check must run on every event, and remember that each check adds about 0.5 s.

**Can Sensibility pick the right skill or tool for Claude?**
Not today. Someone built this as a Jev hook ([`shimo4228/jev-skill-router`](https://github.com/shimo4228/jev-skill-router)). The author concluded it doesn't help a strong model, because Claude already sees every skill's description. It also cost 10k to 25k tokens and up to 1.6 s on every prompt.

**Do I still need TypeSafe's `typesafe-ai` skill?**
Only if you're writing an app that calls Jev from its own code. That skill teaches TypeSafe's SDKs. Sensibility is for Claude calling Jev while it works, and it doesn't use that skill.

**How much does it cost, and how slow is it?**
One judgment (several questions answered together) takes about 0.5 s and costs about $0.00005. With the Risk gate on, 50 Bash commands cost about $0.003 in total. The plugin adds about 189 tokens to each Claude session.

**What happens if my key is missing or Jev is down?**
The judge skill prints the setup steps and stops. The gates switch themselves off and show one message per session. Neither gate ever blocks your work because of a missing key, a network error or a slow answer.

**A check came back `blocked`. Why?**
TypeSafe's web firewall rejects some shell text, such as curl flags or paths like `/etc/passwd`. In testing that was 4 of 164 real commands. Claude rewords the text and tries once more. The gates let the command through.

**Why do the numbers change a little between runs?**
Jev's answers wander by a few hundredths between identical calls. The built-in thresholds are set away from where real answers cluster, so the verdict stays the same.

**Why is the Finish gate on and the Risk gate off?**
The Finish gate costs nothing unless it fires. In testing on 51 real turns, the Finish gate fired 3 times and was right about once; each wrong nudge costs one extra Claude turn. The Risk gate adds about 0.5 s to every Bash command, so it's opt-in. It stops force pushes, `DROP TABLE` and `rm -rf ~`. On 100 real Bash commands its current rules asked once, down from 7 with the first version; the 6 it no longer asks about were `gh` writes the user had requested.

**What leaves my machine, and what's logged?**
For each gate judgment, your last prompt plus the command or reply being judged goes to TypeSafe's API. Each gate judgment is also appended to `judgments.jsonl` under `~/.claude/plugins/data/` (you can delete it any time). Judge skill calls aren't logged. If your prompts or commands must stay on your machine, turn both gates off.

## License

MIT. See [LICENSE](LICENSE).
