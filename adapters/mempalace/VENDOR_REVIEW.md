# Vendor review: MemPalace (`mempalace`)

Status: **invited 2026-09-01, window open until 2026-09-15. The leaderboard row is HELD.**

🔁 This line used to read *"adapter landed, awaiting the pre-review window. Nothing has been run
and no number exists."* That was true when written on 2026-08-29 and stopped being true when
`protocol-025` ran and its numbers were discussed publicly. Corrected rather than deleted, because
the more useful fact is that the window opened AFTER a run rather than before one, which is the
opposite of what the section below promises.

What is being done about it: MemPalace's row is withheld from the leaderboard until the window
closes or the vendor waives it, so the review lands before the canonical record carries anything.
That is enforced by `VENDOR_REVIEW_HOLDS` in `scripts/build_leaderboard.py` and by five tests, not
by this paragraph. This file states every judgement call the adapter makes, so MemPalace's maintainers can
dispute any of them before a run is preregistered rather than after a number is published.

Wired against `mempalace==3.8.0` (PyPI, released 2026-08-23), measured 2026-08-29 on Windows 11,
Python 3.14.6.

## How the arm is wired

| surface | what it is |
|---|---|
| **Retrieval** | the published stdio MCP server, `mempalace-mcp --palace <palace>` |
| **Ingest** | the published CLI, `mempalace --palace <palace> mine <feed> --mode convos --wing bench` |
| **Isolation** | one palace directory per namespace; the palace and the feed are deleted and rebuilt on every ingest |
| **Instruction** | `adapters/_shared/memory_protocol.md` verbatim, one sentence naming `mempalace_search`, plus `instruction_appendix.md` (750 bytes, cap 1,200) |
| **Admission** | the `mcp__mempalace__` prefix must appear in the session's tool list |

The frozen config is `config.frozen.json`, and its sha256 is published in every session record.

## Four judgement calls, stated so they can be disputed

**1. Ingest goes through `--mode convos`, not the harness markdown render.**
The corpus is Claude Code session transcripts, and MemPalace parses them natively. Handing it the
harness's flattened markdown instead would bypass the conversation extraction that is the product.
Verified: 8 corpus sessions filed 56 drawers in 30.7 s. If you would rather be measured on
`--mode projects` over the render, say so and we will run that instead, or both as labelled
variants.

**2. Twenty of your forty-four tools are allowed into a graded session.**
The twenty are the read and navigation surface: `mempalace_search`, the drawer readers, the
knowledge-graph queries, the traversal tools. Every **write** tool is withheld.

This is not a judgement about MemPalace. The corpus is frozen after ingest and no runner currently
calls `MemoryAdapter.snapshot`/`restore`, so a session that wrote to the palace would change the
store the next seed reads, and the arm would be measured against a store that drifted under it.
The same restriction applies to recall, whose arm is allowed two read tools out of its own larger
surface. When per-session restore is wired, this is the first thing to revisit. If you believe
withholding writes materially understates the product, that is exactly the kind of objection this
window is for.

**3. MemPalace gets its own virtualenv, required by `MEMPALACE_VENV` and never guessed.**
It pulls chromadb, onnxruntime and numpy. Resolving those into the environment recall's server runs
from could move recall's pins, and an arm that quietly degrades a *different* arm is worse than an
arm that does not run.

**4. The palace path is refused above 120 characters.**
Not a preference. onnxruntime's `_pybind11_state` DLL fails to load from a deep path on Windows
with `DLL load failed ... The filename or extension is too long`, and chromadb catches that
ImportError and re-raises it as **"The onnxruntime python package is not installed"** when it is
installed. Under the harness's own staging root the venv sat about 260 characters deep and every
embed call failed. Left alone, MemPalace would have scored zero with nothing in the record naming
the reason. The adapter refuses the path instead, and `scripts/mempalace_preflight.py` checks it
before a run starts.

This is upstream's issue #1455 territory. If a future release loads the DLL differently, tell us
and the guard goes.

## What is held fixed, and is not ours to tune either

`--max-chunks-per-file` is left at your default. It exists for exactly the Windows ONNX
`bad_alloc` this corpus could plausibly hit, and setting it would be us tuning your product. If it
should be set, tell us the value and we will freeze it in the config with your name on it.

## Cost accounting

MemPalace makes no hosted call, so its `llm_input_tokens` and `llm_output_tokens` are **0**. That
zero is published together with `local_model` and `wall_time_ms`, because a bare `0` against a
competitor's six figures reads as "this one ingests for free", and it does not: it pays in host
compute. Ingest wall time is where that cost appears.

## The standing offers

Unchanged from `adapters/VENDOR_REVIEW_TEMPLATE.md`: sponsored credits for your arm's traffic, and
a vendor-tuned variant run as an additional labelled arm. What is not on offer is vendor-executed
cells in the canonical table.

## Reproducing the wiring today

```bash
python -m venv C:/mpb/v && C:/mpb/v/Scripts/python -m pip install mempalace==3.8.0
MEMPALACE_VENV=C:/mpb/v MEMPALACE_PALACE_ROOT=C:/mpb/palaces \
  python scripts/mempalace_preflight.py --ingest-smoke
```


## Record

| date | event |
|---|---|
| 2026-09-01 | invitation sent: https://github.com/MemPalace/mempalace/issues/2414 |
| 2026-09-15 | window closes unless extended |

⛔ **The row stays off the board until this window closes or MemPalace waives it.** Removing
`mempalace` from `VENDOR_REVIEW_HOLDS` is the deliberate act that publishes it, and it should be
done at the moment somebody confirms the window actually closed rather than merely elapsed. The
hold is keyed on presence rather than on a date comparison for exactly that reason.

### Vendor response, verbatim

(none received)
