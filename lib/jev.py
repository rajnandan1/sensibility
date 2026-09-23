import json
import os
import sys
import time
import urllib.error
import urllib.request

MODEL = os.environ.get("TYPESAFE_DEFAULT_MODEL") or "jev-1.13.0"
BASE_URL = os.environ.get("TYPESAFE_BASE_URL") or "https://api.typesafe.ai"
STATE_BUDGET = 32000
TOTAL_BUDGET = 64000
RETRY_BUDGET_S = 10.0

KEY_MESSAGE = (
    "TYPESAFE_API_KEY is missing or rejected. Get a key at https://console.typesafe.ai/keys, "
    "then add `export TYPESAFE_API_KEY=...` to ~/.zshenv and restart Claude Code."
)


class JevError(Exception):
    def __init__(self, kind, message, exit_code):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.exit_code = exit_code

    def as_json(self):
        return {"error": self.kind, "message": self.message}


def tokens(value):
    text = value if isinstance(value, str) else json.dumps(value)
    return int(len(text) / 3.5)


def check_budget(state, questions):
    state_tokens = tokens(state)
    longest = max((tokens(q) for q in questions.values()), default=0)
    total = state_tokens + sum(tokens(q) for q in questions.values())
    if state_tokens + longest > STATE_BUDGET or total > TOTAL_BUDGET:
        raise JevError(
            "budget",
            f"About {state_tokens + longest} tokens of state plus longest question (limit {STATE_BUDGET}) "
            f"and {total} total (limit {TOTAL_BUDGET}). Filter the state to what the questions need; "
            "never truncate it blindly.",
            1,
        )


def ask(state, questions, timeout=10.0, retries=3):
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise JevError("key", KEY_MESSAGE, 2)
    check_budget(state, questions)
    body = json.dumps({"state": state, "model": MODEL, "questions": questions}).encode()
    deadline = time.monotonic() + RETRY_BUDGET_S
    delay = 0.5
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            f"{BASE_URL}/v1/systemone",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                reply = json.load(resp)
            reply["ms"] = int((time.monotonic() - started) * 1000)
            return reply
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 403 and detail.lstrip().startswith("<"):
                raise JevError("blocked", "TypeSafe's web firewall rejected this state (HTTP 403, HTML page). "
                               "Remove or paraphrase shell snippets such as curl flags or system paths and retry once.", 1)
            if e.code in (401, 403):
                raise JevError("key", KEY_MESSAGE, 2)
            if e.code in (429, 529) and attempt < retries:
                wait = float(e.headers.get("retry-after") or delay)
                if time.monotonic() + wait < deadline:
                    time.sleep(wait)
                    delay *= 2
                    continue
            if e.code in (429, 529):
                raise JevError("busy", f"Jev is busy (HTTP {e.code}) after retries. Try again shortly.", 3)
            raise JevError("request", f"HTTP {e.code}: {detail}", 1)
        except (urllib.error.URLError, TimeoutError) as e:
            raise JevError("network", f"Could not reach {BASE_URL}: {e}", 1)
    raise JevError("busy", "Jev is busy after retries. Try again shortly.", 3)


def fail(err):
    print(json.dumps(err.as_json()))
    sys.exit(err.exit_code)
