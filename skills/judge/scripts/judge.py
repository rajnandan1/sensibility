#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
import battery as batteries  # noqa: E402
import jev  # noqa: E402


def git_diff(rng):
    if rng.startswith("-"):
        raise jev.JevError("state", f"--git-diff takes a range such as main...HEAD, not `{rng}`.", 1)
    run = subprocess.run(["git", "diff", rng], capture_output=True, text=True)
    if run.returncode != 0:
        raise jev.JevError("state", f"git diff {rng} failed: {run.stderr.strip()}", 1)
    if not run.stdout:
        raise jev.JevError("state", f"git diff {rng} is empty.", 1)
    return run.stdout


def inside_cwd(raw):
    path = Path(raw).resolve()
    if Path.cwd().resolve() not in path.parents:
        raise jev.JevError("state", f"--state-file {raw} is outside the working directory.", 1)
    return path


def keyed_files(files):
    state = {}
    for spec in files:
        key, _, raw = spec.partition("=")
        if not raw:
            raise jev.JevError("state", f"Mix of key=path and bare --state-file: `{spec}`.", 1)
        state[key] = inside_cwd(raw).read_text()
    return state


def read_state(inline, files, rng):
    if rng:
        if inline is not None:
            raise jev.JevError("state", "--git-diff combines only with --state-file key=path.", 1)
        return {**keyed_files(files), "diff": git_diff(rng)}
    if inline is not None and files:
        raise jev.JevError("state", "Use --state or --state-file, not both.", 1)
    if inline is not None:
        try:
            return json.loads(inline)
        except json.JSONDecodeError:
            return inline
    if not files:
        raise jev.JevError("state", "No state: pass --state '<text or json>' or --state-file.", 1)
    if len(files) == 1 and "=" not in files[0]:
        text = inside_cwd(files[0]).read_text()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return keyed_files(files)


def main():
    p = argparse.ArgumentParser(prog="judge.py")
    p.error = lambda message: jev.fail(jev.JevError("usage", message, 1))
    p.add_argument("questions", nargs="?", help="questions JSON, or a battery name")
    p.add_argument("--state")
    p.add_argument("--state-file", action="append", default=[])
    p.add_argument("--git-diff", metavar="RANGE")
    p.add_argument("--list", action="store_true")
    args = p.parse_args()

    if args.list:
        batteries.list_all()
        return

    try:
        battery = None
        if args.questions and args.questions.lstrip().startswith("{"):
            questions = json.loads(args.questions)
        elif args.questions:
            found = batteries.find(args.questions)
            if not found:
                raise jev.JevError("battery", f"No battery `{args.questions}`. Run with --list.", 1)
            battery = json.loads(found[1].read_text())
            questions = battery["questions"]
        else:
            raise jev.JevError("usage", "Pass questions JSON or a battery name.", 1)

        state = read_state(args.state, args.state_file, args.git_diff)
        if battery:
            missing = [k for k in battery["state"].get("keys", []) if not isinstance(state, dict) or k not in state]
            if missing:
                raise jev.JevError("state", f"Battery `{args.questions}` needs state keys {missing}.", 1)

        reply = jev.ask(state, questions)
    except json.JSONDecodeError as e:
        jev.fail(jev.JevError("usage", f"Questions are not valid JSON: {e}", 1))
    except jev.JevError as e:
        jev.fail(e)

    out = {"answers": reply["answers"], "model": reply["model"], "ms": reply["ms"]}
    if battery and "gate" in battery:
        out["verdict"], out["rule"] = batteries.gate(battery["gate"], reply["answers"])
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
