"""The names every arm sees for corpus documents: neutral, and derived only from the corpus path.

Until 2026-09-26 a rendered document was named from its path (``sessions__ts-x__stale_y.md``) and
titled with its stem, so a planted document told the agent its role, its task and whether it was
filler. recall returned that name as ``source`` in 112 of 112 rival and 80 of 80 stale hits in the
published runs, and fs_grep and mempalace showed it too. `superseded` and `contradictory` exist to
test whether an agent notices bad memory without being told, and a name saying ``stale_`` is being
told. A neutral name carries no role, no task and no origin.

Kept free of harness imports so every module that must agree on a name (the renderer, lineage,
graph metadata, the adapters that join hits back) can import it without a cycle.

The salt is public and fixed on purpose. Names must be deterministic, because the corpus
fingerprint is part of every run's provenance, and the participant never sees this repository or
the corpus layout, so a secret salt would protect nothing a public one does not. Bumping the
version changes every fingerprint, which is the point of versioning it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from pathlib import Path

NAME_SALT = "amb-neutral-name-v1"
NEUTRAL_PREFIX = "notes__"
NEUTRAL_NAME = re.compile(r"^notes__[0-9a-f]{16}(?:\.md|\.jsonl)?$")


def neutral_stem(rel: str) -> str:
    """The name, without suffix, that every arm sees for the corpus document at ``rel``."""

    key = Path(rel).as_posix()
    digest = hashlib.sha256(f"{NAME_SALT}:{key}".encode()).hexdigest()[:16]
    return f"{NEUTRAL_PREFIX}{digest}"


def rendered_name(source: Path, root: Path | None = None) -> str:
    """The file name `render_corpus` gives ``source``: neutral, and unique per corpus path."""

    rel = source.relative_to(root).as_posix() if root is not None else source.name
    return neutral_stem(rel) + ".md"


def neutral_token(kind: str, value: str, length: int = 12) -> str:
    """A stable, opaque token for ``value``, namespaced by ``kind`` so tokens never collide."""

    return hashlib.sha256(f"{NAME_SALT}:{kind}:{value}".encode()).hexdigest()[:length]


def condition_namespace(namespace: str, condition: str) -> str:
    """The product namespace for one corpus condition, without the condition's name in it.

    It used to be ``<namespace>-<condition>``, and products echo their namespace back: Graphiti
    returned ``amb-graphiti-official-007-superseded`` 280 times in its superseded tool outputs. An
    agent told which condition it is in knows what kind of trap the corpus holds.
    """

    return f"{namespace}-c{neutral_token('condition', condition, 8)}"


def work_dir_name(run_id: str) -> str:
    """The directory a run's sessions work in, without the run id, which names the condition.

    Every session's working directory is shown to the agent, and it was
    ``<work root>/<run_id>-<condition>/work/...``: the condition name reached every arm, controls
    included, in every run executed on the host.
    """

    return f"run-{neutral_token('run', run_id)}"


def arm_dir_name(arm: str) -> str:
    """The per-arm directory inside a session's working directory, without the arm's name.

    The working directory is shown to the agent, and it ended in the arm name, so a `placebo`
    session saw `placebo` in its own path. A control that announces itself is a weaker control.
    """

    return f"a{neutral_token('arm', arm, 8)}"


def names_a_condition(value: str, conditions: Iterable[str]) -> str | None:
    """The first corpus condition named inside ``value``, or None."""

    lowered = value.lower()
    return next((c for c in conditions if c.lower() in lowered), None)


def neutral_key_map(keys: Iterable[str], suffix: str = ".md") -> dict[str, str]:
    """Neutral file name to corpus key, for joining what an arm returns back to the corpus.

    The inverse lives here and is computed from the manifest in memory. It is never written beside
    a rendered feed: fs_grep serves its feed inside the agent's workspace, and a mapping file there
    would hand back exactly what the neutral names take away.
    """

    return {neutral_stem(key) + suffix: key for key in keys}
