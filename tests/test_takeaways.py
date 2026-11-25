#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import os
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp()).resolve()
_spec = importlib.util.spec_from_file_location("takeaways", REPO / "skills/takeaways/scripts/takeaways.py")
takeaways = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(takeaways)
jev = takeaways.jev
LONG = "one two three four five six seven eight"


def test_chunks_html():
    html = (f"<html><head><style>p {{ x }}</style><script>var a = '{LONG}';</script></head><body>"
            f"<nav>{LONG} menu</nav><h1>Short title</h1><p>{LONG} &amp; first</p><p>{LONG}\n  second</p>"
            f"{LONG} third<br><br>{LONG}<br>fourth<footer>{LONG} footer</footer></body></html>")
    assert takeaways.chunks(html, True) == [f"{LONG} & first", f"{LONG} second", f"{LONG} third", f"{LONG} fourth"]


def test_chunks_text_splits_long_paragraphs():
    text = f"# Heading\n\n{LONG}\nwrapped line\n\n\n" + " ".join(["w"] * 900)
    pieces = takeaways.chunks(text, False)
    assert pieces[0] == f"{LONG} wrapped line"
    assert [len(p.split()) for p in pieces[1:]] == [400, 400, 100]
    assert takeaways.is_html(Path("a.txt"), "<!DOCTYPE html><p>x") and not takeaways.is_html(Path("a.md"), "# x")


def test_score_batches_and_cut():
    calls = []

    def ask(state, questions, timeout):
        calls.append(len(questions))
        return {"answers": {k: {"score": 3.0 if int(k[1:]) % 2 else 1.0} for k in questions}}

    real, jev.ask = jev.ask, ask
    try:
        pieces = [f"{LONG} {i}" for i in range(45)]
        scores = takeaways.score("goal", pieces)
    finally:
        jev.ask = real
    assert sorted(calls) == [5, 20, 20] and len(scores) == 45
    out = takeaways.report("a.md", "goal", pieces, scores)
    assert out.startswith("query: goal\nsource: a.md\nkept: 22 of 45 chunks")
    assert f"[3.00]\n{LONG} 1\n" in out and f"{LONG} 0\n" not in out


def run_main(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
        takeaways.sys.argv = ["takeaways.py", *args]
        takeaways.main()
    return buf.getvalue()


def test_main_refuses_files_outside_cwd():
    (TMP / "work").mkdir()
    (TMP / "secret.txt").write_text(LONG)
    os.chdir(TMP / "work")
    assert '"error": "state"' in run_main("../secret.txt", "goal")
    assert '"error": "usage"' in run_main("a.md")


def test_main_moves_long_output_to_a_file():
    os.chdir(TMP)
    (TMP / "big.md").write_text("\n\n".join(f"{LONG} {i} " + "x " * 300 for i in range(60)))
    real = takeaways.score
    takeaways.score = lambda query, pieces: [3.0] * len(pieces)
    try:
        out = run_main("big.md", "goal")
    finally:
        takeaways.score = real
    path = out.strip().rsplit(" ", 1)[1]
    assert "over the 30000-character output limit" in out and Path(path).read_text().startswith("query: goal")


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("ok", name)
