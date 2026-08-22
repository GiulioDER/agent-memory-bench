"""The corpus leakage audit: every governing fact lives exactly where it claims to.

Three assertions, per task that declares ``fact_terms``:

1. **Presence**: each term appears in at least one of that task's own precursor sessions
   (``corpus/sessions/<task_id>/``). A fact no session states cannot be retrieved by anyone.
2. **Containment**: no term appears in any OTHER task's sessions or in any distractor. A fact
   reachable from two tasks makes their results dependent, and dependence is invisible in the
   per-task analysis.
3. **Locus**: no term appears in the task's fixture tree or in the shared CLAUDE.md bundle.
   A fact derivable without memory measures nothing.

Substring matches are case-insensitive. Exit 1 on any violation, listing all of them; the fix
is to make ``fact_terms`` more distinctive or to move the offending content, never to weaken
the audit.

    python -m scripts.audit_corpus
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.tasks import discover_tasks

BUNDLES = [REPO / "corpus" / "claude_md_bundle_smoke.md"]


def _read_all(paths: list[Path]) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8").lower() for path in paths if path.is_file()}


def main() -> int:
    sessions_root = REPO / "corpus" / "sessions"
    distractors = sorted((REPO / "corpus" / "distractors").glob("*.jsonl"))
    violations: list[str] = []
    audited = 0

    tasks = [task for task in discover_tasks() if task.fact_terms]
    for task in tasks:
        own_sessions = sorted((sessions_root / task.task_id).glob("*.jsonl"))
        own_text = " ".join(_read_all(own_sessions).values())
        other_sessions: list[Path] = []
        for other in tasks:
            if other.task_id != task.task_id:
                other_sessions.extend(sorted((sessions_root / other.task_id).glob("*.jsonl")))
        fixture_files = [path for path in (task.path / "tree").rglob("*") if path.is_file()]
        outside = _read_all(other_sessions + distractors + fixture_files + BUNDLES)

        for term in task.fact_terms:
            needle = term.lower()
            if own_sessions and needle not in own_text:
                violations.append(
                    f"{task.task_id}: term {term!r} appears in NONE of its own sessions"
                )
            for path, text in outside.items():
                if needle in text:
                    violations.append(
                        f"{task.task_id}: term {term!r} leaked into {path.relative_to(REPO)}"
                    )
        if not own_sessions:
            print(f"  note: {task.task_id} has no recorded sessions yet; presence unchecked")
        audited += 1

    if violations:
        print(f"\nLEAKAGE: {len(violations)} violation(s) across {audited} task(s)")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print(f"clean: {audited} task(s) audited, no term outside its own sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
