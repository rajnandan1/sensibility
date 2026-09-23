# Sensibility

A Claude Code plugin that lets Claude ask [Jev](https://docs.typesafe.ai), TypeSafe's judgment model, for typed answers while it works: yes/no probabilities, pick-one-of, and scores on described levels. Jev answers in about half a second for a fraction of a cent, and never generates text.

What you get:

- **`/sensibility:judge`**, a skill Claude uses on its own to rank options, check a diff against its ticket, check a commit message, or score how clear a description reads. Built-in batteries: `scope`, `commit`, `clarity`.
- **Risk gate**, on by default. Every Bash command is judged before it runs. When a command is both risky and destructive, or risky and outside what you asked for, Claude Code asks you first. Everything else runs as normal. Adds about 0.5 s per Bash call.
- **Finish gate**, off by default. When Claude's final reply stops short of what you asked (offers to do the work instead of doing it, asks permission you already gave, ends on a plan), it gets one nudge to carry on.

Both gates fail open: no key, a network error, or a slow answer never blocks your work.

## Requirements

- Claude Code (tested on 2.1.280).
- `python3` on the PATH (3.9 or later, stdlib only). On macOS: `xcode-select --install`.
- A TypeSafe API key.

## Set the key

1. Get a key at https://console.typesafe.ai/keys.
2. Add it to your shell environment, e.g. in `~/.zshenv`:

   ```sh
   export TYPESAFE_API_KEY=...
   ```

3. Restart Claude Code.

Without the key, the judge skill tells you exactly this and stops, and the gates switch themselves off with one message per session.

## Install

Clone it, then try it for one session:

```sh
git clone https://github.com/rajnandan1/sensibility ~/Code/sensibility
claude --plugin-dir ~/Code/sensibility
```

Load it in every session, with no marketplace, as a skills-directory plugin:

```sh
ln -s ~/Code/sensibility ~/.claude/skills/sensibility
```

It then shows up as `sensibility@skills-dir`. To stop loading it, remove the link or run `claude plugin disable sensibility@skills-dir`.

## Turn the gates on or off

Both options live in your user settings (`~/.claude/settings.json`), under the plugin's id: `sensibility@skills-dir` for the symlink install, `sensibility@inline` for `--plugin-dir`.

```json
{
  "pluginConfigs": {
    "sensibility@skills-dir": {
      "options": { "stop_gate": true, "bash_gate": true }
    }
  }
}
```

`stop_gate` is the Finish gate (default `false`); `bash_gate` is the Risk gate (default `true`). Restart Claude Code after changing them.

The Finish gate is off because on real sessions it fired about 3 times in 51 turns with about one true hit, and each false hit costs an extra model turn. Turn it on if Claude often ends turns with "want me to…" on work you already asked for.

## Batteries

A battery is a named set of questions with an optional gate. See them all:

```sh
~/Code/sensibility/skills/judge/scripts/judge.py --list
```

To change a built-in, copy it and edit the copy. A project copy wins over a user copy, which wins over the plugin's:

```sh
mkdir -p ~/.claude/sensibility/batteries
cp ~/Code/sensibility/batteries/scope.json ~/.claude/sensibility/batteries/
```

`risk` and `finish` drive the gates, so they load only from `~/.claude/sensibility/batteries/` or the plugin, never from a project. A repo you clone cannot loosen the Risk gate. The file format is in [skills/judge/reference.md](skills/judge/reference.md).

## What it logs

Every gate judgment is appended to `judgments.jsonl` in the plugin's data directory (`~/.claude/plugins/data/sensibility-skills-dir/` for the symlink install): the state sent, the answers, the verdict, and the latency. That state includes your last prompt and the command or reply judged. Delete the file whenever you like. Judge skill calls are not logged.

Gate states are sent to TypeSafe's API. Turn a gate off if your prompts or commands must not leave the machine.

## License

MIT, see [LICENSE](LICENSE).
