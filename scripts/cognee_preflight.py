"""Prove the `cognee` arm will run, and what it will cost, before a grid spends either.

The admission gate already refuses a cell whose treatment never arrived, which protects the
result. It does not protect the *budget*: a grid that discards every cognee cell has still paid
for every other arm's session in that cell, and cognee is the first arm whose INGEST also has a
bill. This script asks the questions that decide whether the arm can work, in the order they fail,
and each check names the fix rather than the symptom.

    python scripts/cognee_preflight.py
    python scripts/cognee_preflight.py --estimate            # price the real corpus, spend nothing
    python scripts/cognee_preflight.py --ingest-smoke        # also ingest a real subset and search

Exit codes: 0 ready, 1 a check failed, 2 the environment is not configured at all.

Two checks here are not obvious and both were written from the vendor's shipped source rather than
from a failure, which means they are UNVERIFIED against a live install until this script is run:

- **`.env` beats your environment.** `cognee/__init__.py` calls `dotenv.load_dotenv(override=True)`
  at import, searching upward from the working directory, so a stray `.env` silently overrides the
  model, the embedder and the database paths while the run record still names the frozen config.
- **A half-configured cognee bills OpenAI.** `EmbeddingConfig` defaults to
  `openai/text-embedding-3-large`, and per the vendor's `.env` template an unset embedding key
  reuses `LLM_API_KEY`, so setting only the LLM ships every embedding to a provider nobody chose.

`--estimate` is the check worth running before any preregistration: it prints cognee's own dry-run
token and cost estimate for the corpus the run will actually use, without making a single LLM call.
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

from adapters.cognee.adapter import CogneeAdapter, parse_driver_report
from harness.adapters.base import CorpusManifest
from harness.transcripts import render_corpus

CONFIG = json.loads(
    (REPO / "adapters" / "cognee" / "config.frozen.json").read_text(encoding="utf-8")
)
DRIVER = REPO / "adapters" / "cognee" / "ingest_driver.py"

OK, BAD = "  OK  ", " FAIL "


def report(ok: bool, headline: str, detail: str = "") -> bool:
    print(f"[{OK if ok else BAD}] {headline}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    return ok


def check_venv(adapter: CogneeAdapter) -> bool:
    """The venv exists, holds both entry points, and holds the PINNED versions."""

    try:
        python = adapter._venv_bin("python")
        adapter._venv_bin(str(CONFIG["mcp_entrypoint"]))
    except RuntimeError as exc:
        return report(False, "cognee virtualenv", str(exc))

    show = (
        "import importlib.metadata as m;"
        "print(m.version('cognee'), m.version('cognee-mcp'))"
    )
    result = subprocess.run(
        [str(python), "-c", show], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return report(False, "cognee importable", result.stderr[-400:])
    found = result.stdout.split()
    wanted = [
        str(CONFIG["package_pin"]).split("==")[-1],
        str(CONFIG["mcp_package_pin"]).split("==")[-1],
    ]
    if found != wanted:
        return report(
            False,
            f"cognee versions {found}",
            f"the frozen config pins {wanted}. A run against a different version is not "
            f"comparable to one against the pin; either install the pin or move the pin "
            f"deliberately and say so in the run record.",
        )
    return report(True, f"cognee {found[0]} / cognee-mcp {found[1]} in {python.parent.parent}")


def check_embedder(adapter: CogneeAdapter) -> bool:
    """fastembed loads AND is the configured provider. This is the MAX_PATH trap's second home."""

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
                "onnxruntime DLL. Rebuild it somewhere short, e.g. C:/cgn/v."
            )
        return report(False, "onnxruntime loads (fastembed's engine)", tail + hint)
    if str(CONFIG["embedding"]["provider"]) != "fastembed":
        return report(
            False,
            "embedding provider is not fastembed",
            "the frozen config names a different provider, so this check is looking at the "
            "wrong engine. Update the check with the config, not around it.",
        )
    return report(True, f"onnxruntime {result.stdout.strip()} loads (local embedder)")


def check_store_path(adapter: CogneeAdapter, namespace: str) -> bool:
    try:
        store = adapter._store_dir(namespace)
    except RuntimeError as exc:
        return report(False, "store path length", str(exc))
    return report(True, f"store path fits ({len(str(store.absolute()))} chars): {store}")


def check_no_stray_dotenv(adapter: CogneeAdapter, namespace: str) -> bool:
    """No `.env` cognee would load, because it would win against the frozen config.

    Both roots are checked: the venv, which is where `find_dotenv` starts in a normal run, and
    the store, which is the working directory and is what applies under a debugger.
    """

    store = adapter._store_dir(namespace)
    store.mkdir(parents=True, exist_ok=True)
    try:
        adapter.refuse_stray_dotenv(adapter._venv(), store)
    except RuntimeError as exc:
        return report(False, "no .env overrides the frozen config", str(exc))
    return report(True, f"no .env at or above {adapter._venv()} or {store}")


def check_configuration(adapter: CogneeAdapter, namespace: str) -> bool:
    """Every setting that decides what is billed is present, and the key is not in the repo."""

    try:
        env = adapter.cognee_env(namespace)
    except RuntimeError as exc:
        return report(False, "cognee configuration", str(exc))
    required = (
        "LLM_PROVIDER", "LLM_MODEL", "LLM_ENDPOINT", "LLM_API_KEY",
        "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS",
        "DATA_ROOT_DIRECTORY", "SYSTEM_ROOT_DIRECTORY",
    )
    missing = [key for key in required if not env.get(key)]
    if missing:
        return report(
            False,
            f"{len(missing)} required setting(s) unset",
            "missing: " + ", ".join(missing)
            + "\ncognee defaults an unset embedding pair to OpenAI and reuses LLM_API_KEY for it, "
              "so a partial configuration bills a provider nobody chose.",
        )
    frozen = (REPO / "adapters" / "cognee" / "config.frozen.json").read_text(encoding="utf-8")
    if env["LLM_API_KEY"] in frozen:
        return report(
            False,
            "the API key is in the frozen config",
            "config.frozen.json is published and vendor-reviewed. The key is read from "
            f"{CONFIG['llm']['api_key_env']} and must never be written into it.",
        )
    return report(
        True,
        f"extraction {env['LLM_MODEL']} at {env['LLM_ENDPOINT']}, "
        f"embedding {env['EMBEDDING_PROVIDER']}/{env['EMBEDDING_MODEL']}",
    )


def check_mcp_tools(adapter: CogneeAdapter, namespace: str) -> bool:
    """Every tool the frozen config allows still exists on the server it will be served by.

    A vendor rename between versions would otherwise surface as the agent never using its memory,
    which the gate ADMITS as a behavioural result. That would publish a wiring fault as a finding
    about discoverability, which is the one mistake this benchmark cannot afford to make.
    """

    server = adapter._venv_bin(str(CONFIG["mcp_entrypoint"]))
    env = adapter.cognee_env(namespace)
    adapter._store_dir(namespace).mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [str(server), "--transport", "stdio"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1, env=env,
        cwd=str(adapter._store_dir(namespace)),
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
              "adapters/cognee/config.frozen.json rather than the server."
            + f"\nServed: {', '.join(sorted(served)) or '(none)'}",
        )
    return report(
        True,
        f"MCP server {version} serves {len(served)} tools, "
        f"all {len(CONFIG['allowed_tools'])} allowed ones present",
    )


def check_estimate(adapter: CogneeAdapter, corpus_root: Path, namespace: str) -> bool:
    """Price the real corpus with cognee's own estimator. Spends nothing.

    This is the check that makes the arm affordable to plan: the previous third-party arm's
    ingest cost was discovered by paying it, and this one can be read first.
    """

    corpus = CorpusManifest.load(corpus_root)
    store = adapter._store_dir(namespace)
    feed = adapter._feed_dir(namespace)
    for stale in (store, feed):
        if stale.exists():
            shutil.rmtree(stale)
    store.mkdir(parents=True, exist_ok=True)
    rendered = render_corpus(
        [corpus.root / rel for rel in sorted(corpus.sessions)], feed, root=corpus.root
    )
    print(f"         estimating {rendered} rendered document(s); no LLM call is made")
    result = subprocess.run(
        [
            str(adapter._venv_bin("python")), str(DRIVER), str(feed),
            adapter.dataset(namespace), str(float(CONFIG["ingest_cost_ceiling_usd"])),
            "--estimate-only",
        ],
        cwd=str(store), env=adapter.cognee_env(namespace),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    estimate = dict((parse_driver_report(result.stdout) or {}).get("estimate") or {})
    if not estimate:
        return report(
            False, "dry-run estimate", (result.stderr or result.stdout)[-800:]
        )
    cost = float(estimate.get("estimated_cost_usd") or 0.0)
    ceiling = float(CONFIG["ingest_cost_ceiling_usd"])
    detail = (
        f"model {estimate.get('model')}\n"
        f"chunks {estimate.get('chunks')}, "
        f"input {estimate.get('input_tokens')}, output {estimate.get('output_tokens')} tokens\n"
        f"ESTIMATE ${cost:.4f} against the ${ceiling:.2f} ceiling in config.frozen.json\n"
        f"cognee's estimator excludes embeddings and uses output heuristics, so this is a bound "
        f"to decide by, not measured spend."
    )
    for warning in estimate.get("warnings") or []:
        detail += f"\nvendor warning: {warning}"
    return report(
        cost <= ceiling,
        f"ingest of {rendered} document(s) estimated at ${cost:.4f}",
        detail,
    )


#: The smoke ingests this task's precursors and searches for the fact they carry. Chosen as a
#: pair, because a subset that holds no signal session can only ever prove that retrieval returns
#: nothing, and a plain `sorted()[:n]` returns exactly that: `distractors/` sorts before
#: `sessions/`, so the first N entries of this corpus are all distractors.
SMOKE_TASK = "ts-append-only"


def check_ingest_smoke(adapter: CogneeAdapter, corpus_root: Path, sessions: int) -> bool:
    """Ingest a real subset of the real corpus and search it. The only end-to-end proof.

    ⚠️ This one SPENDS: extraction is an LLM pass over every chunk. It is bounded by
    ``--smoke-sessions`` and by the ceiling in the frozen config, and the estimate is printed
    before the spend by ``--estimate``.
    """

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
    staging = Path(tempfile.mkdtemp(prefix="cgn-smoke-"))
    try:
        (staging / "manifest.json").write_text(
            json.dumps({"sessions": subset}), encoding="utf-8"
        )
        for rel in subset:
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(corpus_root / rel, dest)

        print(f"         ingesting {len(subset)} session(s); the first run downloads the embedder")
        ingest = adapter.ingest(CorpusManifest.load(staging), "preflight-smoke")
        return report(
            True,
            f"ingest processed {ingest.items_stored} chunk(s) from "
            f"{ingest.sessions_offered} session(s) in {ingest.wall_time_ms / 1000:.1f}s, "
            f"and the store answered a probe drawn from the corpus",
            f"estimated {ingest.llm_input_tokens} in / {ingest.llm_output_tokens} out tokens "
            f"for extraction; embeddings were local and unbilled",
        )
    except RuntimeError as exc:
        return report(False, "ingest smoke", str(exc))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="preflight")
    parser.add_argument("--corpus-root", default=str(REPO / "corpus"))
    parser.add_argument(
        "--estimate", action="store_true",
        help="price the whole corpus with cognee's dry-run estimator. Makes no LLM call.",
    )
    parser.add_argument(
        "--ingest-smoke", action="store_true",
        help="also ingest a corpus subset and probe it. SPENDS: extraction is an LLM pass.",
    )
    parser.add_argument("--smoke-sessions", type=int, default=4)
    args = parser.parse_args()

    if not os.environ.get(str(CONFIG["venv_env"])):
        print(
            f"[{BAD}] {CONFIG['venv_env']} is unset.\n"
            f"         cognee needs its OWN virtualenv: it pulls litellm, lancedb, kuzu and\n"
            f"         onnxruntime, and resolving those beside another arm could move that arm's\n"
            f"         pins and corrupt a different arm's result. Build it at a SHORT path:\n\n"
            f"           python -m venv C:/cgn/v\n"
            f"           C:/cgn/v/Scripts/python -m pip install \"{CONFIG['package_pin']}\" "
            f"{CONFIG['mcp_package_pin']}\n"
            f"           export {CONFIG['venv_env']}=C:/cgn/v\n"
            f"           export {CONFIG['store_root_env']}=C:/cgn/stores\n"
            f"           export {CONFIG['llm']['api_key_env']}=...\n"
        )
        return 2

    prompt = REPO / "corpus" / "claude_md_bundle_smoke.md"
    adapter = CogneeAdapter(Path(tempfile.gettempdir()) / "cgn-preflight", prompt)

    checks = [
        check_venv(adapter),
        check_embedder(adapter),
        check_store_path(adapter, args.namespace),
        check_no_stray_dotenv(adapter, args.namespace),
        check_configuration(adapter, args.namespace),
    ]
    if all(checks):
        checks.append(check_mcp_tools(adapter, args.namespace))
        if args.estimate and checks[-1]:
            checks.append(check_estimate(adapter, Path(args.corpus_root), args.namespace))
        if args.ingest_smoke and checks[-1]:
            checks.append(check_ingest_smoke(adapter, Path(args.corpus_root), args.smoke_sessions))

    print()
    if all(checks):
        print("cognee arm is ready. Add it with --arms ...,cognee")
        return 0
    print("cognee arm is NOT ready; fix the failure above before spending a grid on it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
