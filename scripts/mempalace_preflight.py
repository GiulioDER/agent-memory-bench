"""Prove the `mempalace` arm will run, before a grid spends credit discovering it will not.

The admission gate already refuses a cell whose treatment never arrived, which protects the
result. It does not protect the *budget*: a grid that discards every mempalace cell has still paid
for every other arm's session in that cell. This script asks the four questions that decide whether
the arm can work, in the order they fail, and each check names the fix rather than the symptom.

    python scripts/mempalace_preflight.py
    python scripts/mempalace_preflight.py --ingest-smoke      # also mine and search a real subset

Exit codes: 0 ready, 1 a check failed, 2 the environment is not configured at all.

The third check is the one that is not obvious. MemPalace embeds through onnxruntime, whose
`_pybind11_state` DLL fails to load from a deep path on Windows with "The filename or extension is
too long". chromadb catches that ImportError and re-raises it as "The onnxruntime python package is
not installed", so the arm dies reporting a missing dependency that is in fact installed. Measured
2026-08-29 against mempalace==3.8.0 with the venv about 260 characters deep.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from adapters.mempalace.adapter import MemPalaceAdapter
from harness.adapters.base import CorpusManifest

CONFIG = json.loads(
    (REPO / "adapters" / "mempalace" / "config.frozen.json").read_text(encoding="utf-8")
)

OK, BAD = "  OK  ", " FAIL "


def report(ok: bool, headline: str, detail: str = "") -> bool:
    print(f"[{OK if ok else BAD}] {headline}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    return ok


def check_venv(adapter: MemPalaceAdapter) -> bool:
    """The venv exists, holds both entry points, and holds the PINNED version."""

    try:
        python = adapter._venv_bin("python")
        adapter._venv_bin(str(CONFIG["mcp_entrypoint"]))
    except RuntimeError as exc:
        return report(False, "MemPalace virtualenv", str(exc))

    show_version = "import mempalace, importlib.metadata as m; print(m.version('mempalace'))"
    result = subprocess.run(
        [str(python), "-c", show_version],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return report(False, "MemPalace importable", result.stderr[-400:])
    found = result.stdout.strip()
    want = str(CONFIG["package_pin"]).split("==")[-1]
    if found != want:
        return report(
            False,
            f"MemPalace version {found}",
            f"the frozen config pins {want}. A run against a different version is not comparable "
            f"to one against the pin; either install the pin or move the pin deliberately and say "
            f"so in the run record.",
        )
    return report(True, f"MemPalace {found} in {python.parent.parent}")


def check_onnx(adapter: MemPalaceAdapter) -> bool:
    """The embedder loads. This is the check that catches the MAX_PATH trap."""

    python = adapter._venv_bin("python")
    result = subprocess.run(
        [str(python), "-c", "import onnxruntime;print(onnxruntime.__version__)"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        tail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
        hint = ""
        if "too long" in result.stderr or "DLL load failed" in result.stderr:
            hint = (
                "\nThis is the path-length trap: the venv is too deep for Windows to load the "
                "onnxruntime DLL. Rebuild it somewhere short, e.g. C:/mpb/v."
            )
        return report(False, "onnxruntime loads", tail + hint)
    return report(True, f"onnxruntime {result.stdout.strip()} loads (local embedder)")


def check_palace_path(adapter: MemPalaceAdapter, namespace: str) -> bool:
    try:
        palace = adapter._palace_dir(namespace)
    except RuntimeError as exc:
        return report(False, "palace path length", str(exc))
    return report(True, f"palace path fits ({len(str(palace.absolute()))} chars): {palace}")


def check_mcp_tools(adapter: MemPalaceAdapter, namespace: str) -> bool:
    """Every tool the frozen config allows still exists on the server it will be served by.

    A vendor rename between versions would otherwise surface as the agent never using its memory,
    which the gate ADMITS as a behavioural result. That would publish a wiring fault as a finding
    about discoverability, which is the one mistake this benchmark cannot afford to make.
    """

    server = adapter._venv_bin(str(CONFIG["mcp_entrypoint"]))
    palace = adapter._palace_dir(namespace)
    palace.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [str(server), "--palace", str(palace)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    try:
        def send(payload: dict) -> None:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()

        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "preflight", "version": "0"}}})
        init = json.loads(proc.stdout.readline())
        version = init.get("result", {}).get("serverInfo", {}).get("version", "?")
        send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        served = {t["name"] for t in json.loads(proc.stdout.readline())["result"]["tools"]}
    except Exception as exc:  # noqa: BLE001 - any failure here is a failed check, reported
        return report(False, "MCP server answers tools/list", f"{type(exc).__name__}: {exc}")
    finally:
        proc.terminate()

    missing = sorted(set(CONFIG["allowed_tools"]) - served)
    if missing:
        return report(
            False,
            f"MCP server {version} is missing {len(missing)} allowed tool(s)",
            "missing: " + ", ".join(missing)
            + "\nEither the pin moved or the vendor renamed a tool. Fix "
              "adapters/mempalace/config.frozen.json rather than the server.",
        )
    return report(
        True,
        f"MCP server {version} serves {len(served)} tools, "
        f"all {len(CONFIG['allowed_tools'])} allowed ones present",
    )


#: The smoke mines this task's precursors and searches for the fact they carry. Chosen as a pair,
#: because a subset that holds no signal session can only ever prove that retrieval returns
#: nothing, and a plain `sorted()[:n]` returns exactly that: `distractors/` sorts before
#: `sessions/`, so the first N entries of this corpus are all distractors.
SMOKE_TASK = "ts-append-only"
SMOKE_QUERY = "append-only audit trail never rewrite past lines"


def check_ingest_smoke(adapter: MemPalaceAdapter, corpus_root: Path, sessions: int) -> bool:
    """Mine a real subset of the real corpus and search it. The only end-to-end proof."""

    full = CorpusManifest.load(corpus_root)
    signal = {k: v for k, v in sorted(full.sessions.items()) if f"/{SMOKE_TASK}/" in k}
    if not signal:
        return report(
            False, f"corpus holds no {SMOKE_TASK} session",
            f"{corpus_root} has no precursor for the task this smoke searches for, so a miss "
            f"would say nothing about retrieval. Point --corpus-root at the real corpus.",
        )
    filler = [item for item in sorted(full.sessions.items()) if item[0] not in signal]
    subset = dict(list(signal.items()) + filler[: max(0, sessions - len(signal))])
    staging = Path(tempfile.mkdtemp(prefix="mp-smoke-"))
    try:
        (staging / "manifest.json").write_text(
            json.dumps({"sessions": subset}), encoding="utf-8"
        )
        for rel in subset:
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(corpus_root / rel, dest)
        smoke_corpus = CorpusManifest.load(staging)

        print(f"         mining {len(subset)} session(s); the first run downloads the model")
        ingest = adapter.ingest(smoke_corpus, "preflight-smoke")
        report(
            True,
            f"ingest filed {ingest.items_stored} drawer(s) from "
            f"{ingest.sessions_offered} session(s) in {ingest.wall_time_ms / 1000:.1f}s",
        )

        python = adapter._venv_bin("python")
        query = SMOKE_QUERY
        result = subprocess.run(
            [str(python), "-m", str(CONFIG["cli_module"]),
             "--palace", str(adapter._palace_dir("preflight-smoke")),
             "search", query, "--results", "3"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode != 0:
            return report(False, "search answers", result.stderr[-400:])
        if "Source:" not in result.stdout:
            return report(
                False, "search returned no hits",
                f"query {query!r} matched nothing in a freshly filled palace, which means "
                f"retrieval is not working rather than that the corpus lacks the fact.",
            )
        hits = result.stdout.count("Source:")
        return report(True, f"search for {query!r} returned {hits} hit(s)")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="preflight")
    parser.add_argument("--corpus-root", default=str(REPO / "corpus"))
    parser.add_argument(
        "--ingest-smoke", action="store_true",
        help="also mine a corpus subset and search it. Slow on the first run: the embedding "
             "model is ~79 MB and is downloaded once.",
    )
    parser.add_argument("--smoke-sessions", type=int, default=4)
    args = parser.parse_args()

    if not os.environ.get(str(CONFIG["venv_env"])):
        print(
            f"[{BAD}] {CONFIG['venv_env']} is unset.\n"
            f"         MemPalace needs its OWN virtualenv: it pulls chromadb, onnxruntime and "
            f"numpy,\n"
            f"         and resolving those beside recall could move recall's pins and corrupt a\n"
            f"         different arm's result. Build it at a SHORT path:\n\n"
            f"           python -m venv C:/mpb/v\n"
            f"           C:/mpb/v/Scripts/python -m pip install {CONFIG['package_pin']}\n"
            f"           export {CONFIG['venv_env']}=C:/mpb/v\n"
            f"           export {CONFIG['palace_root_env']}=C:/mpb/palaces\n"
        )
        return 2

    prompt = REPO / "corpus" / "claude_md_bundle_smoke.md"
    adapter = MemPalaceAdapter(Path(tempfile.gettempdir()) / "mp-preflight", prompt)

    checks = [
        check_venv(adapter),
        check_onnx(adapter),
        check_palace_path(adapter, args.namespace),
    ]
    if all(checks):
        checks.append(check_mcp_tools(adapter, args.namespace))
        if args.ingest_smoke and checks[-1]:
            checks.append(check_ingest_smoke(adapter, Path(args.corpus_root), args.smoke_sessions))

    print()
    if all(checks):
        print("mempalace arm is ready. Add it with --arms ...,mempalace")
        return 0
    print("mempalace arm is NOT ready; fix the failure above before spending a grid on it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
