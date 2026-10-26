#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp()).resolve()
os.environ["CLAUDE_CONFIG_DIR"] = str(TMP / "config")
_spec = importlib.util.spec_from_file_location("which", REPO / "skills/which/scripts/which.py")
which = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(which)
jev = which.jev


def write(path, text):
    path = TMP / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_scan():
    write("config/skills/plain/SKILL.md", "---\nname: plain\ndescription: \"Plain one. More.\"\n---\nbody\n")
    write("config/skills/hidden/SKILL.md", "---\ndescription: >\n  Folded line one\n  line two.\ndisable-model-invocation: true\n---\n")
    write("config/skills/nobody/SKILL.md", "---\ndescription: x\nuser-invocable: false\n---\n")
    write("config/skills/bodyonly/SKILL.md", "---\nname: bodyonly\n---\n\nFirst body line.\n")
    write("config/skills/synced/bundle/docs/SKILL.md", "---\nname: docs\ndescription: Docs.\n---\n")
    write("config/commands/go.md", "---\ndescription: Go.\n---\n")
    write("config/commands/sub/deep.md", "---\ndescription: Deep.\n---\n")
    write("config/commands/bare.md", "no frontmatter\n")
    write("plugins/tool/skills/outline/SKILL.md", "---\nname: tool-outline\ndescription: Outline.\nwhen_to_use: When asked.\n---\n")
    write("plugins/tool/commands/run.md", "---\ndescription: Run.\n---\n")
    write("plugins/off/skills/gone/SKILL.md", "---\ndescription: Gone.\n---\n")
    write("config/plugins/installed_plugins.json", json.dumps({"plugins": {
        "tool@market": [{"installPath": str(TMP / "plugins/tool")}],
        "off@market": [{"installPath": str(TMP / "plugins/off")}],
    }}))
    write("config/settings.json", json.dumps({"enabledPlugins": {"off@market": False}}))
    write("project/.claude/skills/local/SKILL.md", "---\ndescription: Local.\n---\n")
    write("project/.claude/skills/plain/SKILL.md", "---\ndescription: Shadowed.\n---\n")
    (TMP / "project/.git").mkdir()
    (TMP / "project/src").mkdir()

    roster = {s["name"]: s["description"] for s in which.scan(TMP / "project/src")}
    assert roster == {
        "plain": "Plain one. More.",
        "hidden": "Folded line one line two.",
        "bodyonly": "First body line.",
        "anthropic-skills:docs": "Docs.",
        "go": "Go.",
        "sub:deep": "Deep.",
        "local": "Local.",
        "tool:tool-outline": "Outline. When asked.",
        "tool:run": "Run.",
    }, roster


def test_questions():
    roster = [{"name": n, "description": f"{n} does it."} for n in ("d", "a", "c", "b", "deeper", "ken:ken")]
    qs = which.questions(roster)
    assert list(qs) == ["h0", "h1", "deeper", "ready"], list(qs)
    assert list(qs["h0"]["criteria"]) == ["a", "c", "none"]
    assert list(qs["h1"]["criteria"]) == ["b", "d", "none"]
    assert qs["deeper"] is which.LENSES["deeper"]["noul"]
    assert "ready" not in which.questions(roster[:4])


def answers(h0, h1, **nouls):
    choice = lambda probs: {"choice": max(probs, key=probs.get), "probabilities": probs}
    return {"h0": choice(h0), "h1": choice(h1), **{n: {"noul": v} for n, v in nouls.items()}}


def test_pick():
    roster = [{"name": "a", "description": "Does a. Then more."}, {"name": "b", "description": ""}, {"name": "c", "description": "C."},
              {"name": "d", "description": "Does d"}]
    usage = {"a": 10, "c": 1}
    task = answers({"a": 0.5, "c": 0.1, "none": 0.4}, {"b": 0.6, "none": 0.4}, deeper=0.2, ready=0.1)
    assert which.pick("fix it", task, roster, usage) == ["/a fix it", "why: Does a. You ran it 10 times.", "runner-up: /b"]
    weak = answers({"none": 0.7, "a": 0.2}, {"none": 0.8, "b": 0.15})
    assert which.pick("hm", weak, roster, {"b": 1})[1:] == ["why: You ran it 1 time.", "runner-up: /a", which.WEAK_MATCH]
    heavy = answers({"a": 0.28, "none": 0.48}, {"d": 0.08, "none": 0.48})
    assert which.pick("start x", heavy, roster, {"a": 11, "d": 301})[:3] == ["/a start x", "why: Does a. You ran it 11 times.", "runner-up: /d"]
    assert which.pick("start x", heavy, roster, {"d": 301})[1] == "why: Does d. You ran it 301 times."
    below_none = answers({"none": 0.37, "c": 0.2, "d": 0.13}, {"a": 0.8, "none": 0.13, "b": 0.02})
    assert which.pick("work on x", below_none, roster, {"a": 69, "d": 2}) == ["/a work on x", "why: Does a. You ran it 69 times."]
    new_skill = answers({"c": 0.9, "none": 0.1}, {"a": 0.8, "none": 0.2})
    new_skill["final"] = {"choice": "c", "probabilities": {"c": 0.9, "a": 0.1, "none": 0.0}}
    assert which.pick("do x", new_skill, roster, {"a": 69}) == ["/c do x", "why: C. You ran it 0 times.", "runner-up: /a"]
    new_skill["final"]["probabilities"] = {"c": 0.96, "a": 0.01, "none": 0.03}
    assert which.pick("do x", new_skill, roster, {"a": 69}) == ["/c do x", "why: C. You ran it 0 times."]
    lens = answers({"a": 0.5, "none": 0.5}, {"b": 0.6, "none": 0.4}, deeper=0.8, wider=0.75, ready=0.2)
    assert which.pick("make x", lens, roster, usage) == [
        "/deeper make x",
        f"why: {which.LENSES['deeper']['why']}",
        "next: Run /sensibility:which on the rewrite that /deeper gives you.",
        "skip the Lens: /a make x",
    ]
    lens["ready"]["noul"] = 0.5
    assert which.pick("make x", lens, roster, usage)[0] == "/a make x"


def test_main_sends_context():
    states = []

    def ask(state, questions):
        states.append(state)
        raise jev.JevError("busy", "", 3)

    real_ask, real_argv = jev.ask, which.sys.argv
    jev.ask = ask
    try:
        for argv in (["--context", " T: body ", "start X-1"], ["start X-1"]):
            which.sys.argv = ["which.py", *argv]
            try:
                which.main()
            except SystemExit:
                pass
    finally:
        jev.ask, which.sys.argv = real_ask, real_argv
    assert states == [{"prompt": "start X-1", "context": "T: body"}, {"prompt": "start X-1"}]


def test_main_asks_final_round_for_two_finalists():
    roster = [{"name": n, "description": f"{n} does it."} for n in ("a", "b", "c")]
    asked, first = [], {}

    def ask(state, questions):
        asked.append({name: list(q["criteria"]) for name, q in questions.items()})
        if "final" in questions:
            return {"answers": {"final": {"choice": "b", "probabilities": {"a": 0.2, "b": 0.7, "none": 0.1}}}}
        return {"answers": first}

    def run(h0, h1):
        first.clear()
        first.update(answers(h0, h1))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            which.main()
        return out.getvalue().splitlines()[0]

    real_ask, real_scan, real_argv = jev.ask, which.scan, which.sys.argv
    jev.ask, which.scan, which.sys.argv = ask, lambda cwd: roster, ["which.py", "x"]
    try:
        assert run({"a": 0.5, "c": 0.1, "none": 0.4}, {"b": 0.6, "none": 0.4}) == "/b x"
        assert asked[1] == {"final": ["a", "b", "none"]}, asked
        assert run({"a": 0.3, "c": 0.1, "none": 0.6}, {"b": 0.6, "none": 0.4}) == "/b x"
        assert len(asked) == 3, asked
    finally:
        jev.ask, which.scan, which.sys.argv = real_ask, real_scan, real_argv


def hook(command):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_PLUGIN_OPTION_")}
    run = subprocess.run([str(REPO / "hooks/sensibility-pretooluse-risk")], input=json.dumps({"tool_input": {"command": command}}),
                         capture_output=True, text=True, env={**env, "CLAUDE_PLUGIN_ROOT": "/plug"})
    return json.loads(run.stdout)["hookSpecificOutput"]["permissionDecision"] if run.stdout else None


def test_hook_allows_quoted_prompt():
    script = "/plug/skills/which/scripts/which.py "
    assert hook(script + "'it'\\''s `ls` and $(id)\nline two'") == "allow"
    assert hook(script + "--context 'T: `/agent/query` $x' 'start X-1'") == "allow"
    assert hook("/plug/skills/judge/scripts/judge.py --list") == "allow"
    assert hook(script + "'a'; rm -rf ~") is None
    assert hook(script + "$(id)") is None
    assert hook(script + "'a'\nrm -rf ~") is None
    assert hook("/plug/skills/other/scripts/which.py 'a'") is None


def test_jev_retries_oserror():
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionResetError(54, "Connection reset by peer")
        return io.BytesIO(b'{"answers": {}}')

    os.environ["TYPESAFE_API_KEY"] = os.environ.get("TYPESAFE_API_KEY") or "test"
    real = jev.urllib.request.urlopen
    jev.urllib.request.urlopen = urlopen
    try:
        assert jev.ask("s", {})["answers"] == {} and len(calls) == 2
    finally:
        jev.urllib.request.urlopen = real


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok", name)
