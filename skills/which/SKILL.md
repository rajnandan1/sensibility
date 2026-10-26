---
name: which
description: Pick the skill to put in front of your prompt. Type /sensibility:which <prompt>. It prints the line to paste, one reason and, when a second skill fits, one runner-up.
argument-hint: <prompt>
disable-model-invocation: true
---

# Which

If the prompt names a ticket, issue, pull request or link that one of your tools can read, such as a Linear id, read it first. Read only the title and the description, and read nothing else.

Then run exactly this one Bash command, with the prompt at the end of this file as its last argument:

```
${CLAUDE_PLUGIN_ROOT}/skills/which/scripts/which.py --context '<title and description>' '<prompt>'
```

- Leave out `--context '<title and description>'` when the prompt names nothing you can read, or when the read fails.
- Copy the prompt exactly as typed, newlines included, inside the single quotes. Write each `'` in either argument as `'\''`.
- Nothing else goes on the line: no `;`, `&&`, `|`, `>`, `<`, `$(...)`, env prefixes or `cd`. The plugin's hook allows only this shape.

Print the script's output exactly, inside one code block, and add nothing. Do not run the skill it picks.

## Errors

- Exit 2, `{"error":"key",...}`: relay `message` to the user verbatim and stop. Do not retry, do not look for keys.
- Exit 3, `{"error":"busy"}`: tell the user Jev is busy. Do not retry.
- Any other error: show its `message` and stop.

## Prompt

$ARGUMENTS
