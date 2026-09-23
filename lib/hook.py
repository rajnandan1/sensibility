import json
import os
import sys
import time
from pathlib import Path

import battery as batteries
import jev

DATA = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude/sensibility")
TIMEOUT_S = 3.0


def enabled(option, default):
    return os.environ.get(f"CLAUDE_PLUGIN_OPTION_{option}", default).lower() in ("true", "1", "on")


def last_prompt(transcript_path):
    try:
        lines = Path(transcript_path).read_text().splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "user" or entry.get("isMeta"):
            continue
        content = entry.get("message", {}).get("content")
        if isinstance(content, str):
            return content
        if any(block.get("type") == "tool_result" for block in content or []):
            continue
        text = "\n".join(b.get("text", "") for b in content or [] if b.get("type") == "text")
        if text:
            return text
    return ""


def log(record):
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "judgments.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def key_warning_once(session_id):
    marker = DATA / f"key-warned-{session_id}"
    if marker.exists():
        return None
    DATA.mkdir(parents=True, exist_ok=True)
    marker.touch()
    return {"systemMessage": f"Sensibility gates are off for this session. {jev.KEY_MESSAGE}"}


def judge(name, state, event, skip=()):
    found = batteries.find(name)
    battery = json.loads(found[1].read_text())
    started = time.monotonic()
    record = {"ts": time.time(), "session": event.get("session_id"), "event": event.get("hook_event_name"),
              "battery": name, "state": state}
    try:
        questions = {q: spec for q, spec in battery["questions"].items() if q not in skip}
        reply = jev.ask(state, questions, timeout=TIMEOUT_S, retries=0)
    except jev.JevError as e:
        record.update(error=e.kind, wall_ms=int((time.monotonic() - started) * 1000))
        log(record)
        if e.kind == "key":
            return None, key_warning_once(event.get("session_id"))
        return None, None
    verdict, rule = batteries.gate(battery["gate"], reply["answers"])
    record.update(answers=reply["answers"], verdict=verdict, rule=rule, jev_ms=reply["ms"],
                  wall_ms=int((time.monotonic() - started) * 1000), usage=reply.get("usage"))
    log(record)
    return (verdict, rule, reply["answers"]), None


def emit(output):
    if output:
        print(json.dumps(output))


def run(main):
    try:
        main(json.load(sys.stdin))
    except Exception:
        pass
    sys.exit(0)
