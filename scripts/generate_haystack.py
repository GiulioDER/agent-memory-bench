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
not been challenged. So the haystack is four tiers, and the last two exist because **a lexical
ranker and a semantic ranker are fooled by different documents**, measured in
`preregistration/015-corpus-scale-retrieval-difficulty.md`:

* **background** (default 60%): a generated repository in a domain the task suite does not
  legislate, doing mundane work. This is the volume. It costs BM25 nothing and costs an
  embedder rank depth.
* **topical** (15%): the same, in a repository whose subject area overlaps the general
  vocabulary of software conventions (encodings, ordering, configuration, logs, identifiers).
  Zero competitors against BM25; the single largest competitor source against `voyage-4`.
* **near_miss** (10%): a repository seeded with the content words of ONE task's prompt. The
  LEXICAL hard negative: 72.5% of BM25's competitors at 9.6% of the corpus, and only 33.0% of
  Voyage's.
* **semantic** (15%): the SAME meaning neighbourhood as one task, in deliberately different
  words, sharing no distinctive token with that task's prompt at all, and settling a question
  on an axis the task does not ask about. That last rule is what keeps a hard negative from
  becoming a `contradictory` plant.

  ⚠️ It has TWO vocabularies and ``--semantic-generation`` chooses between them, because the
  first one FAILED. Generation 2 (`haystack_neighbourhoods.py`) measured 0.57x competitor yield
  against `voyage-4` in preregistration 016, BELOW its population share, because removing every
  shared word and moving to an orthogonal axis left business-process prose against
  technical-convention prompts. Generation 3 (`haystack_neighbourhoods_v3.py`) keeps the axis
  and changes the register. Both are kept so the claim is testable with one variable moving.

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
from scripts.haystack_neighbourhoods import NEIGHBOURHOODS
from scripts.haystack_neighbourhoods_v3 import NEIGHBOURHOODS_V3
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
DEFAULT_MIX = {"background": 0.60, "topical": 0.15, "near_miss": 0.10, "semantic": 0.15}

#: Emission order. `background` absorbs the rounding remainder in `_tier_counts`, so it goes
#: last only in the mix dict and first here; the order itself is fixed so a file index maps to
#: the same session for a given seed no matter what the shares are set to.
TIERS = ("background", "topical", "near_miss", "semantic")

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
    """sha256 over this module, its vocabulary AND the task data, so a plan names its inputs.

    "The code that produced it" was too narrow, and the omission was exactly the class of input
    the comment below warns about. `make_session` draws near-miss vocabulary from `task.prompt`
    and `_fact_phrases` from `task.fact_terms`, so editing a task's prompt changes what every
    near-miss session in the haystack says while leaving `generator_sha256` untouched: two
    corpora with the same digest and different text, which is the one thing a digest exists to
    prevent. Only the two fields that reach the generator are hashed, so unrelated task metadata
    does not churn the digest for no reason.
    """

    # Every file whose CONTENT decides what a session says has to be in here. The neighbourhood
    # data was added to the generator before it was added to this list, which would have let a
    # `haystack.json` claim a corpus was reproducible while the text inside it moved.
    material = b"".join(
        (REPO / "scripts" / name).read_bytes()
        for name in (
            "generate_haystack.py",
            "haystack_vocab.py",
            "haystack_neighbourhoods.py",
            "haystack_neighbourhoods_v3.py",
        )
    )
    task_material = json.dumps(
        {
            task.task_id: {"prompt": task.prompt, "fact_terms": sorted(task.fact_terms)}
            for task in sorted(discover_tasks(), key=lambda item: item.task_id)
        },
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(material + task_material).hexdigest()


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


#: A semantic near-miss frames its request on the SUBJECT, never on a term list. The terms are
#: what the document ends up saying; putting them in the request would smuggle the task's
#: neighbourhood into the query side of the comparison as well, which is not what is being asked.
SEMANTIC_REQUESTS: tuple[str, ...] = (
    (
        "Write {target} for {project}. It should cover {subject}, because it came up in review "
        "again and nobody could point at where it is written down."
    ),
    (
        "{project} needs {target}. Please record {subject}, and say which files it applies to "
        "so the next person does not have to ask."
    ),
    (
        "Put together {target} for {project}, covering {subject}. Keep it to what is true of "
        "this repository rather than what we do elsewhere."
    ),
    (
        "We settled {subject} last week and it is not recorded anywhere. Write it into "
        "{target} for {project} with enough context to be useful in six months."
    ),
)


def session_events(
    rng: random.Random,
    project: dict,
    theme: dict,
    subject: str | None,
    date: datetime,
    near_terms: tuple[str, ...] = (),
    neighbourhood: dict | None = None,
) -> list[dict]:
    """One session: a real request, real reads of the generated tree, a real write, a summary."""

    files = project["files"]
    data_name = project["data_name"]
    target = theme["target"] if theme["target"].endswith(".md") else "report.py"
    listing = "\n".join(f"./{name}" for name in sorted(files))
    request = theme["prompt"]
    if neighbourhood is not None:
        # A semantic near-miss asks its own question, framed on the SUBJECT rather than on any
        # word the task's prompt uses. Reusing the near-miss templates here would have injected
        # the term list into the request and quietly turned this back into a lexical negative.
        request = rng.choice(SEMANTIC_REQUESTS).format(
            project=project["name"], target=target, subject=neighbourhood["subject"]
        )
    elif len(near_terms) >= 3:
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
    if neighbourhood is not None:
        terms = list(neighbourhood["terms"])
        rng.shuffle(terms)
        written += (
            f"\n## {str(neighbourhood['subject'])[0].upper()}{str(neighbourhood['subject'])[1:]}\n"
            f"\nThis came up again in review, so it is written down here rather than left to "
            f"whoever remembers it.\n\n"
            f"**What we settled:** {neighbourhood['decision']}.\n\n"
            f"The words that keep coming up when this is discussed are {', '.join(terms[:6])}, "
            f"and they mean the following for {project['name']} specifically:\n\n"
            + "".join(
                f"- **{term}** as it applies to `{data_name}` and to `report.py`\n"
                for term in terms[:5]
            )
            + f"\nNone of this is a rule for any other repository. It describes what "
            f"{project['name']} does with its own files, and a different service is free to "
            f"have settled the same question differently.\n"
        )
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


def make_session(
    index: int, seed: int, tier: str, tasks: list, *, semantic_generation: int = 3
) -> tuple[list[dict], dict]:
    """Generate session ``index`` of a batch. Pure in ``(index, seed, tier, generator)``.

    ``semantic_generation`` selects which neighbourhood vocabulary the `semantic` tier draws on.
    Generation 2 is `scripts/haystack_neighbourhoods.py`, measured at 0.57x competitor yield
    against `voyage-4` in preregistration 016: business-process prose against technical prompts.
    Generation 3 is `scripts/haystack_neighbourhoods_v3.py`, which keeps the orthogonal axis and
    changes the register. Both are kept so the contrast can be re-measured with one variable
    moving, which is the only way the register claim is testable rather than asserted.
    """

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
    elif tier == "semantic":
        # Same meaning neighbourhood, deliberately different words. `NEIGHBOURHOODS` carries no
        # token from the task's own prompt, so this tier competes on meaning or not at all,
        # which is exactly the discrimination `near_miss` could not test.
        book = NEIGHBOURHOODS_V3 if semantic_generation == 3 else NEIGHBOURHOODS
        candidates = [task for task in tasks if task.task_id in book]
        task = candidates[rng.randrange(len(candidates))]
        near_task = task.task_id
        neighbourhood = book[task.task_id]
        extra = tuple(neighbourhood["terms"])  # type: ignore[arg-type]
        subject = str(neighbourhood["subject"])
    project = build_project(rng, domain, extra)
    date = WINDOW_START + timedelta(days=rng.randrange(WINDOW_DAYS))
    events = session_events(
        rng,
        project,
        theme,
        subject,
        date,
        near_terms=extra if tier == "near_miss" else (),
        neighbourhood=(
            (NEIGHBOURHOODS_V3 if semantic_generation == 3 else NEIGHBOURHOODS)[near_task]
            if tier == "semantic"
            else None
        ),
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
    # The docstring is this script's `--help` text and carries the house-style U+26D4 / U+26A0
    # markers, so `--help` died with a UnicodeEncodeError on a cp1252 console: the script was
    # undocumented on Windows and fine on Linux, which is the failure this project has hit in
    # both directions already. Replacing unencodable characters degrades the marker rather than
    # the command, and is scoped to this process's own streams.
    for stream in (sys.stdout, sys.stderr):
        if getattr(stream, "reconfigure", None) and (stream.encoding or "").lower() not in (
            "utf-8",
            "utf8",
        ):
            stream.reconfigure(errors="replace")
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
        "--topical-share", type=float, default=DEFAULT_MIX["topical"], help="Default 0.15."
    )
    parser.add_argument(
        "--semantic-share",
        type=float,
        default=DEFAULT_MIX["semantic"],
        help="fraction generated from a task's SEMANTIC neighbourhood, sharing no prompt "
        "vocabulary at all. Default 0.15.",
    )
    parser.add_argument(
        "--semantic-generation",
        type=int,
        choices=(2, 3),
        default=3,
        help="which neighbourhood vocabulary the semantic tier draws on. 2 is the "
        "business-process register measured at 0.57x yield in preregistration 016; 3 keeps the "
        "orthogonal axis and moves to technical-convention register. Default 3.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="regenerate in memory and compare against the written haystack.json; write nothing",
    )
    parser.add_argument("--force", action="store_true", help="overwrite an existing root")
    args = parser.parse_args()

    # Per share AND the sum. Validating only the sum let `--near-miss-share -0.5
    # --topical-share 0.7` through: `_tier_counts` then yields a negative count, the emit loop is
    # simply skipped, and the negative fraction is written into `plan["mix"]` as provenance for a
    # tier that was never built. A silently empty tier is worse than a refusal, because the plan
    # still describes it.
    shares = {
        "--near-miss-share": args.near_miss_share,
        "--topical-share": args.topical_share,
        "--semantic-share": args.semantic_share,
    }
    for flag, value in shares.items():
        if not 0.0 <= value <= 1.0:
            raise SystemExit(f"{flag} must be between 0.0 and 1.0, got {value}")
    adversarial = args.near_miss_share + args.topical_share + args.semantic_share
    if not 0.0 <= adversarial <= 1.0:
        raise SystemExit(
            f"topical, near-miss and semantic shares must sum to at most 1.0, got {adversarial}"
        )

    tasks = [task for task in discover_tasks() if task.fact_terms]
    phrases = _fact_phrases(tasks)
    real = CorpusManifest.load(BASE_CORPUS)
    base_documents = len(real.sessions)
    target_total = args.scale * base_documents
    synthetic_total = max(0, target_total - base_documents)
    mix = {
        "near_miss": args.near_miss_share,
        "topical": args.topical_share,
        "semantic": args.semantic_share,
        "background": 1.0 - adversarial,
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
    for tier in TIERS:
        made = 0
        attempt = 0
        while made < counts[tier]:
            events, provenance = make_session(
                attempt, args.seed, tier, tasks,
                semantic_generation=args.semantic_generation,
            )
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
        "semantic_generation": args.semantic_generation,
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

        # ---- and now the BYTES, which the key comparison above never touched ----------------
        #
        # `haystack.json` is written by this same generator, so comparing the plan against it
        # compares this code with a record of this code. Every file the plan describes could be
        # truncated, half-written or absent and `--check` would still print OK. That matters more
        # here than it would elsewhere: the haystack root is GITIGNORED, so git can never notice
        # the damage either, and the probe reads these files as the corpus a published retrieval
        # number was measured over.
        problems: list[str] = []
        expected: dict[str, str] = {}
        for rel, events, _provenance in emitted:
            body = "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n"
            expected[rel] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        for base_dir in ("sessions", "distractors"):
            for path in sorted((BASE_CORPUS / base_dir).rglob("*.jsonl")):
                rel = path.relative_to(BASE_CORPUS).as_posix()
                expected[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

        for rel, digest in expected.items():
            path = out / rel
            if not path.is_file():
                problems.append(f"MISSING   {rel}")
            elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                problems.append(f"CORRUPT   {rel}")
        # Extra files are a mismatch in the other direction, and the one a count-based check is
        # blindest to: a stale document from an earlier scale is a real document the probe would
        # rank, belonging to no plan.
        for path in sorted(out.rglob("*.jsonl")):
            rel = path.relative_to(out).as_posix()
            if rel not in expected:
                problems.append(f"UNPLANNED {rel}")

        if problems:
            print(f"MISMATCH on bytes: {len(problems)} file(s) differ from the plan")
            for line in problems[:20]:
                print(f"  {line}")
            if len(problems) > 20:
                print(f"  ... and {len(problems) - 20} more")
            return 1
        print(
            f"OK  {out} matches this generator "
            f"({plan['total_documents']} documents, {len(expected)} files verified by sha256)"
        )
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
