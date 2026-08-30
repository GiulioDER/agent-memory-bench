"""Assemble a large corpus root: the real feed plus a synthetic haystack around it.

    python -m scripts.generate_haystack --scale 25 --seed 1
    python -m scripts.generate_haystack --scale 25 --seed 1 --check

Why this exists
---------------

`docs/reviews/2026-08-30-instrument-review.md` section 4: the bench corpus is 951 to 1,129
chunks, an order of magnitude smaller than one real memory store, and the ``hit@1 = 20/20``
cited in preregistration 014 to justify disabling a reranker is not evidence that retrieval is
solved. It is evidence that the corpus holds too few competitors for ranking to matter. A metric
that cannot go down has not measured anything.

**Corpus scale is the only lever that raises difficulty for the memory arms without moving
`bare`**, because a distractor session changes nothing a memory-free agent can see.

What this writes, and what it does NOT touch
--------------------------------------------

An assembled root under ``corpus/haystack/scale-<N>/seed-<S>/``, in the same shape
``scripts/assemble_condition_corpus.py`` established, so ``CorpusManifest.build`` and every
adapter work against it unchanged::

    sessions/<task_id>/*.jsonl     the real precursors, copied byte for byte
    distractors/*.jsonl            the 156 real recorded distractors, copied byte for byte
    synthetic/h#####.jsonl         the generated haystack
    manifest.json                  sha256 of all three
    haystack.json                  provenance: scale, seed, tier mix, counts, generator digest

``corpus/manifest.json`` is never rewritten, so the frozen 195-entry feed every published run
used stays exactly as it is and a haystack run is visibly a different corpus rather than a
quiet redefinition of the old one.

⛔ **Synthetic sessions are not recorded agent output and are never mixed into
``corpus/distractors/``.** Rule 1 of ``corpus/README.md`` ("content is verbatim agent output")
holds for the real feed and does not hold here; keeping them in their own directory, under
their own manifest, with their own provenance file, is what makes that distinction survive
somebody reading the tree six months from now.

What makes a synthetic session hard rather than merely numerous
---------------------------------------------------------------

Bulk alone does not test ranking. Ten thousand sessions about hive inspections do not compete
with a query about CRLF line endings on export, and a retriever that ignores all of them has
not been challenged. So the haystack is three tiers:

* **background** (default 70%): a generated repository in a domain the task suite does not
  legislate, doing mundane work. This is the volume, and it is what makes the index big.
* **topical** (20%): the same, in a repository whose subject area overlaps the general
  vocabulary of software conventions (encodings, ordering, configuration, logs, identifiers),
  so a query lands in a populated neighbourhood rather than an empty one.
* **near-miss** (10%): a repository seeded with the content words of ONE task's prompt, doing
  mundane work and settling a small convention about its own artefacts. This is the hard
  negative, and it is generated **from the query vocabulary itself**, which is the only
  construction that reliably competes with the gold document for a lexical ranker.

Containment holds by construction and is checked anyway
--------------------------------------------------------

A near-miss is built from the task's PROMPT, and ``scripts/audit_corpus.py`` assertion 3
(locus) already guarantees no fact term appears in a prompt. So prompt vocabulary is safe
vocabulary. Every emitted file is nevertheless re-checked against every task's ``fact_terms``
with the same normalisation the real audit uses, and a violating session is discarded and
regenerated. A guarantee nobody tests is a hope.

Reproducibility
---------------

Generation is a pure function of ``(scale, seed, generator digest)``. ``--check`` regenerates
into memory and compares against a written ``haystack.json``, so a haystack does not have to be
committed to be verifiable: 25x is roughly 25 MB of transcripts and a 400 KB manifest, and the
plan plus the digest reproduce it byte for byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.adapters.base import CorpusManifest
from harness.plants import normalise
from harness.tasks import discover_tasks
from scripts.audit_corpus import _STOP
from scripts.haystack_vocab import DOMAINS, LOCAL_CONVENTIONS, SUMMARY_OPENERS, THEMES

BASE_CORPUS = REPO / "corpus"
HAYSTACK_ROOT = BASE_CORPUS / "haystack"

#: Matches `scripts/record_precursor.py`, so a synthetic session is indistinguishable in SHAPE
#: from a recorded one. Shape, not provenance: `haystack.json` records what it really is.
TURN_SECONDS = 40
DAY_START_HOUR = 9

#: Sessions are dated across this window so the haystack reads as months of history rather than
#: one afternoon, matching how the real feed is stamped (corpus/README.md rule 2).
WINDOW_START = datetime(2026, 2, 2, tzinfo=UTC)
WINDOW_DAYS = 200

#: Tier mix. Background is the volume; near-miss is the difficulty. Overridable on the command
#: line so the difficulty curve can be measured against the mix as well as against the size.
DEFAULT_MIX = {"background": 0.70, "topical": 0.20, "near_miss": 0.10}

#: General software-convention vocabulary, used by the `topical` tier only. None of these
#: phrases is any task's fact term; they are the NEIGHBOURHOOD a task's fact lives in, which is
#: what a query has to be discriminated from.
TOPICAL_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("encoding", "text encoding and how the files are decoded when they are read back"),
    ("ordering", "the order rows come out in when the report is regenerated"),
    ("configuration", "where settings are read from and which source wins"),
    ("logging", "what the run writes to its log and at which level"),
    ("identifiers", "how the record identifiers are formed and how long they are"),
    ("timestamps", "which clock the timestamps are taken from and how they are formatted"),
    ("tabular export", "how the exported table quotes and separates its columns"),
    ("retries", "what the client does when the upstream call does not answer"),
    ("generated files", "which files in the tree are produced by a tool rather than written"),
    ("paths", "whether paths are recorded relative to the repository or absolute"),
)


def _digest_generator() -> str:
    """sha256 over this module and its vocabulary, so a plan names the code that produced it."""

    material = b"".join(
        (REPO / "scripts" / name).read_bytes()
        for name in ("generate_haystack.py", "haystack_vocab.py")
    )
    return hashlib.sha256(material).hexdigest()


def _rng(*parts: object) -> random.Random:
    """A generator seeded by content, so a session does not depend on the order it was made in."""

    key = "|".join(str(part) for part in parts)
    return random.Random(int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16))


def prompt_terms(prompt: str) -> list[str]:
    """The content words of a task prompt, longest first.

    Safe as near-miss vocabulary by construction: `scripts/audit_corpus.py` assertion 3 already
    asserts that no fact term appears in any task prompt, so nothing derived from a prompt can
    reintroduce one.
    """

    words = [w.strip(".,:;()'\"") for w in normalise(prompt).split()]
    seen: dict[str, None] = {}
    for word in words:
        if len(word) > 3 and word not in _STOP and not word.isdigit():
            seen.setdefault(word, None)
    return sorted(seen, key=lambda w: (-len(w), w))[:14]


# --------------------------------------------------------------------------------------------
# The generated repository. Tool results below are real reads of these strings, so the bulk of
# a session's bytes is genuine file content rather than narration about file content.
# --------------------------------------------------------------------------------------------


def build_project(rng: random.Random, domain: dict, extra_terms: tuple[str, ...]) -> dict:
    """One small repository: a README, a data file and a report script."""

    slug = str(domain["slug"])
    entities = tuple(domain["entities"])  # type: ignore[arg-type]
    fields = tuple(domain["fields"])  # type: ignore[arg-type]
    verbs = tuple(domain["verbs"])  # type: ignore[arg-type]
    suffix = rng.choice(("", "-ops", "-core", "-tools", "-svc", "2"))
    name = f"{slug}{suffix}"
    data_name = rng.choice((f"{entities[0]}s.jsonl", f"{entities[0]}_log.jsonl", "records.jsonl"))

    rows = []
    for index in range(rng.randint(5, 9)):
        row = {fields[0]: f"{entities[0][:2].upper()}-{100 + index * rng.randint(1, 4)}"}
        row[fields[1]] = rng.choice((entities[1], entities[2], entities[3]))
        row[fields[2]] = rng.choice(("open", "closed", "pending", "held", str(rng.randint(1, 90))))
        row[fields[3]] = f"2026-0{rng.randint(1, 8)}-{rng.randint(10, 28)}T0{rng.randint(1, 9)}:00:00Z"
        rows.append(json.dumps(row))
    data_text = "\n".join(rows) + "\n"

    mention = ""
    if extra_terms:
        picked = ", ".join(extra_terms[: rng.randint(4, 7)])
        mention = (
            f"\nOperational notes from the last review mention {picked}. Those notes are kept "
            f"with the team wiki and are not tracked here.\n"
        )

    readme = (
        f"# {name}\n\n"
        f"{name} handles {domain['title']} for a single region. Records arrive as JSON lines in\n"
        f"`{data_name}` and are turned into a plain-text report by `report.py`.\n\n"
        f"Each record describes one {entities[0]}: which {entities[1]} it belongs to, its current\n"
        f"state, and when it was recorded. Operators {verbs[0]} new rows through the intake form\n"
        f"and the nightly job will {verbs[1]} anything left untouched for a week.\n\n"
        f"## Files\n\n"
        f"- `{data_name}` - one {entities[0]} per line\n"
        f"- `report.py` - reads the data file and prints a summary\n"
        f"- `README.md` - this file\n"
        f"{mention}"
    )

    report = (
        "import json\n"
        "import sys\n\n\n"
        "def load(path):\n"
        "    with open(path, encoding='utf-8') as handle:\n"
        "        return [json.loads(line) for line in handle if line.strip()]\n\n\n"
        "def summarise(rows):\n"
        "    counts = {}\n"
        f"    for row in rows:\n"
        f"        key = row.get('{fields[1]}', 'unknown')\n"
        "        counts[key] = counts.get(key, 0) + 1\n"
        "    return counts\n\n\n"
        "def main():\n"
        f"    rows = load(sys.argv[1] if len(sys.argv) > 1 else '{data_name}')\n"
        "    for key, count in sorted(summarise(rows).items()):\n"
        f"        print(key.ljust(16), count)\n"
        "    # TODO: the report has no header row yet\n\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    return {
        "name": name,
        "data_name": data_name,
        "entities": entities,
        "fields": fields,
        "verbs": verbs,
        "title": str(domain["title"]),
        "files": {"README.md": readme, data_name: data_text, "report.py": report},
    }


def _numbered(text: str, limit: int = 24) -> str:
    """A Read tool result: the file's real bytes, line numbered, as Claude Code returns them."""

    lines = text.splitlines()[:limit]
    return "\n".join(f"{index + 1}\t{line}" for index, line in enumerate(lines))


def _written_artifact(
    rng: random.Random, project: dict, theme: dict, subject: str | None
) -> str:
    """The file the session actually produces. Real content, written into the real tree."""

    name = project["name"]
    entities = project["entities"]
    fields = project["fields"]
    about = f" It also records how the team handles {subject}." if subject else ""
    key = theme["key"]
    if key in ("overview", "structure-review", "layout"):
        return (
            f"# {name} - overview\n\n"
            f"{name} covers {project['title']}. The data file holds one {entities[0]} per line\n"
            f"and `report.py` groups them by {fields[1]} for the daily summary.{about}\n\n"
            f"New code belongs beside `report.py` at the top level; there is no package layout\n"
            f"and adding one for three files would cost more than it returns.\n"
        )
    if key == "data-dictionary":
        rows = "\n".join(f"- `{field}` - {field.replace('_', ' ')}" for field in fields[:4])
        return f"# Data\n\n`{project['data_name']}` fields:\n\n{rows}\n{about}\n"
    if key == "domain-terms":
        rows = "\n".join(
            f"- **{entity}** - a single {entity} tracked by {name}" for entity in entities
        )
        return f"# Domain terms\n\n{rows}\n{about}\n"
    if key in ("faq", "smoke-notes", "maintainers", "changelog", "todo-roundup"):
        return (
            f"# {theme['target'].removesuffix('.md')}\n\n"
            f"Run `python report.py {project['data_name']}` and check that the counts add up to\n"
            f"the number of lines in the data file. The only outstanding item is the missing\n"
            f"header row in the report output.{about}\n"
        )
    return (
        f"# {name}\n\n"
        f"## Getting started\n\n"
        f"    python report.py {project['data_name']}\n\n"
        f"The command prints one line per {fields[1]} with the number of {entities[0]}s in it.{about}\n"
    )


#: A near-miss session's own request. The point is that it SHARES THE FRAMING of a task prompt
#: while asking about the generated repository's artefacts, because a query and a document that
#: share framing is the case a ranker actually has to discriminate. A real store is full of
#: these: the same question asked last month about a different repository.
NEAR_MISS_REQUESTS: tuple[str, ...] = (
    (
        "In {project}, write {target} covering how we handle {a}, {b} and {c}. The review "
        "raised all three and none of them is written down. Say which file each one lives in."
    ),
    (
        "{target} for {project} is missing. Record what we settled about {a} and {b}, and note "
        "where {c} is dealt with, so the next person does not have to ask."
    ),
    (
        "Write up {target} for {project}: what {a} means here, how {b} is produced, and what we "
        "do about {c}. Keep it to what is true of this repository."
    ),
    (
        "We keep re-deciding {a} in {project}. Put the current answer in {target}, along with "
        "{b} and {c}, and reference the files they apply to."
    ),
)


def session_events(
    rng: random.Random,
    project: dict,
    theme: dict,
    subject: str | None,
    date: datetime,
    near_terms: tuple[str, ...] = (),
) -> list[dict]:
    """One session: a real request, real reads of the generated tree, a real write, a summary."""

    files = project["files"]
    data_name = project["data_name"]
    target = theme["target"] if theme["target"].endswith(".md") else "report.py"
    listing = "\n".join(f"./{name}" for name in sorted(files))
    request = theme["prompt"]
    if len(near_terms) >= 3:
        picked = rng.sample(list(near_terms), 3)
        request = rng.choice(NEAR_MISS_REQUESTS).format(
            project=project["name"], target=target, a=picked[0], b=picked[1], c=picked[2]
        )
    events: list[dict] = [{"role": "user", "content": request}]
    events.append(
        {
            "role": "assistant",
            "content": "",
            "tool_name": "Bash",
            "tool_input": json.dumps({"command": "ls -1"}),
            "tool_result": listing,
        }
    )
    reads = ["README.md", data_name]
    if rng.random() < 0.7:
        reads.append("report.py")
    rng.shuffle(reads)
    for name in reads:
        events.append(
            {
                "role": "assistant",
                "content": "",
                "tool_name": "Read",
                "tool_input": json.dumps({"file_path": f"./{name}"}),
                "tool_result": _numbered(files[name]),
            }
        )
    written = _written_artifact(rng, project, theme, subject)
    if near_terms:
        listed = ", ".join(near_terms[: min(len(near_terms), rng.randint(6, 10))])
        written += (
            f"\n## What the review raised\n\n"
            f"The points carried over were {listed}. Each is settled for {project['name']} only:\n"
            f"they describe what this repository does with its own files, and nothing here is a\n"
            f"house rule for any other repository. Where a point touches `{data_name}` the answer\n"
            f"is whatever `report.py` already does, since changing it would invalidate the\n"
            f"archived reports nobody has the budget to regenerate.\n"
        )
    events.append(
        {
            "role": "assistant",
            "content": "",
            "tool_name": "Edit" if target in files else "Write",
            "tool_input": json.dumps({"file_path": f"./{target}", "content": written}),
            "tool_result": f"The file ./{target} has been updated successfully.",
        }
    )
    events.append(
        {
            "role": "assistant",
            "content": "",
            "tool_name": "Read",
            "tool_input": json.dumps({"file_path": f"./{target}"}),
            "tool_result": _numbered(written),
        }
    )
    summary = (
        f"{rng.choice(SUMMARY_OPENERS)}\n\n"
        f"- **What {project['name']} is**: {project['title']}, one {project['entities'][0]} per "
        f"line in `{data_name}`, summarised by `report.py`.\n"
        f"- **What I wrote**: `{target}`, covering the files in the listing and how to run the "
        f"report.\n"
        f"- **{rng.choice(LOCAL_CONVENTIONS)}**\n"
    )
    if subject:
        summary += (
            f"- I also wrote down {subject}, because it was decided in review and was not "
            f"recorded anywhere in the repository.\n"
        )
    events.append({"role": "assistant", "content": summary})
    events.append({"role": "user", "content": theme["closing"]})

    stamped = []
    base = date.replace(hour=DAY_START_HOUR, minute=0, second=0, microsecond=0)
    for index, event in enumerate(events):
        moved = dict(event)
        moved["ts"] = (base + timedelta(seconds=TURN_SECONDS * index)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        stamped.append(moved)
    return stamped


def make_session(index: int, seed: int, tier: str, tasks: list) -> tuple[list[dict], dict]:
    """Generate session ``index`` of a batch. Pure in ``(index, seed, tier, generator)``."""

    rng = _rng(seed, tier, index)
    domain = DOMAINS[rng.randrange(len(DOMAINS))]
    theme = THEMES[rng.randrange(len(THEMES))]
    extra: tuple[str, ...] = ()
    subject: str | None = None
    near_task: str | None = None
    if tier == "topical":
        name, subject = TOPICAL_SUBJECTS[rng.randrange(len(TOPICAL_SUBJECTS))]
        extra = (name,)
    elif tier == "near_miss":
        task = tasks[rng.randrange(len(tasks))]
        near_task = task.task_id
        extra = tuple(prompt_terms(task.prompt))
        subject = (
            f"how {extra[0] if extra else 'the report'} is handled for this repository's own "
            f"files, which is a local decision and not a house rule"
        )
    project = build_project(rng, domain, extra)
    date = WINDOW_START + timedelta(days=rng.randrange(WINDOW_DAYS))
    events = session_events(
        rng, project, theme, subject, date, near_terms=extra if tier == "near_miss" else ()
    )
    provenance = {
        "tier": tier,
        "domain": domain["slug"],
        "theme": theme["key"],
        "project": project["name"],
        "near_miss_task": near_task,
        "session_date": date.strftime("%Y-%m-%d"),
    }
    return events, provenance


# --------------------------------------------------------------------------------------------


def _fact_phrases(tasks: list) -> list[tuple[str, str]]:
    return [(task.task_id, normalise(term)) for task in tasks for term in task.fact_terms]


def _violates(text: str, phrases: list[tuple[str, str]]) -> str | None:
    normalised = normalise(text)
    for task_id, phrase in phrases:
        if phrase and phrase in normalised:
            return task_id
    return None


def _tier_counts(total: int, mix: dict[str, float]) -> dict[str, int]:
    counts = {tier: int(total * share) for tier, share in mix.items()}
    counts["background"] += total - sum(counts.values())
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale",
        type=int,
        default=25,
        help="target total documents as a multiple of the real feed (195). Default 25.",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--near-miss-share",
        type=float,
        default=DEFAULT_MIX["near_miss"],
        help="fraction of the haystack generated from task prompt vocabulary. Default 0.10.",
    )
    parser.add_argument(
        "--topical-share", type=float, default=DEFAULT_MIX["topical"], help="Default 0.20."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and compare against the written haystack.json; write nothing",
    )
    parser.add_argument("--force", action="store_true", help="overwrite an existing root")
    args = parser.parse_args()

    if not 0.0 <= args.near_miss_share + args.topical_share <= 1.0:
        raise SystemExit("topical and near-miss shares must sum to at most 1.0")

    tasks = [task for task in discover_tasks() if task.fact_terms]
    phrases = _fact_phrases(tasks)
    real = CorpusManifest.load(BASE_CORPUS)
    base_documents = len(real.sessions)
    target_total = args.scale * base_documents
    synthetic_total = max(0, target_total - base_documents)
    mix = {
        "near_miss": args.near_miss_share,
        "topical": args.topical_share,
        "background": 1.0 - args.near_miss_share - args.topical_share,
    }
    counts = _tier_counts(synthetic_total, mix)

    out = HAYSTACK_ROOT / f"scale-{args.scale}" / f"seed-{args.seed}"
    generator = _digest_generator()

    print(
        f"real feed {base_documents} documents; generating {synthetic_total} synthetic "
        f"({', '.join(f'{tier} {n}' for tier, n in sorted(counts.items()))})"
    )

    emitted: list[tuple[str, list[dict], dict]] = []
    discarded: list[dict] = []
    index = 0
    for tier in ("background", "topical", "near_miss"):
        made = 0
        attempt = 0
        while made < counts[tier]:
            events, provenance = make_session(attempt, args.seed, tier, tasks)
            attempt += 1
            text = " ".join(
                str(event.get(field, ""))
                for event in events
                for field in ("content", "tool_result", "tool_input")
            )
            leaked = _violates(text, phrases)
            if leaked is not None:
                discarded.append({"tier": tier, "leaked": leaked})
                continue
            emitted.append((f"synthetic/h{index:05d}.jsonl", events, provenance))
            index += 1
            made += 1

    plan = {
        "scale": args.scale,
        "seed": args.seed,
        "generator_sha256": generator,
        "mix": mix,
        "counts": counts,
        "real_documents": base_documents,
        "synthetic_documents": len(emitted),
        "total_documents": base_documents + len(emitted),
        "discarded_for_containment": len(discarded),
        # Which tier leaked which task's fact, so a tier that is being silently thinned by the
        # containment filter is visible in the plan rather than inferred from a count.
        "discarded_detail": {
            key: sum(1 for item in discarded if f"{item['tier']}/{item['leaked']}" == key)
            for key in sorted({f"{item['tier']}/{item['leaked']}" for item in discarded})
        },
        "sessions": {rel: provenance for rel, _, provenance in emitted},
    }

    if args.check:
        written = out / "haystack.json"
        if not written.is_file():
            raise SystemExit(f"{written} does not exist; nothing to check against")
        stored = json.loads(written.read_text(encoding="utf-8"))
        for key in ("generator_sha256", "counts", "mix", "sessions", "total_documents"):
            if stored.get(key) != plan[key]:
                print(f"MISMATCH on {key}: the haystack on disk is not what this code produces")
                return 1
        print(f"OK  {out} matches this generator ({plan['total_documents']} documents)")
        return 0

    if out.exists():
        if not args.force:
            raise SystemExit(f"{out} exists; pass --force to rebuild it")
        shutil.rmtree(out)
    (out / "synthetic").mkdir(parents=True)
    shutil.copytree(BASE_CORPUS / "sessions", out / "sessions")
    shutil.copytree(BASE_CORPUS / "distractors", out / "distractors")
    for rel, events, _ in emitted:
        body = "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n"
        (out / rel).write_text(body, encoding="utf-8", newline="\n")
    (out / "haystack.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    manifest = CorpusManifest.build(out)

    total_bytes = sum(path.stat().st_size for path in out.rglob("*.jsonl"))
    print(
        f"wrote {out}\n"
        f"  documents  {len(manifest.sessions)} "
        f"({base_documents} real, {len(emitted)} synthetic)\n"
        f"  bytes      {total_bytes / 1_048_576:.1f} MB\n"
        f"  discarded  {len(discarded)} for containment\n"
        f"  generator  {generator[:12]}"
    )
    if len(manifest.sessions) != plan["total_documents"]:
        print("WARNING: manifest count differs from the plan; the corpus root was not clean")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
