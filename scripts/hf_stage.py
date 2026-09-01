"""Stage the Hugging Face dataset and Space payloads. Never uploads.

Two publication targets are prepared here and neither is pushed by this script:

    build/hf/dataset/   the experience corpus, plus `huggingface/dataset-card.md` as README.md
    build/hf/space/     the contents of `site/`, plus `huggingface/space-card.md` as README.md

The upload is a separate, deliberate act by a person holding a token, and the commands are printed
at the end rather than run. That separation is the point: a name, a username or a path cannot be
recalled once it has shipped, and a script that both assembles and publishes turns a review step
into a flag.

Staging REFUSES if an undisclosed product name reaches either payload. That guard exists on the
site already (`tests/test_site_vendor_disclosure.py`); it is repeated here because the dataset card
is a second published surface and a guard scoped to one directory is not a guard on the other.

    python scripts/hf_stage.py            stage both, then print the upload commands
    python scripts/hf_stage.py --check    report what would be staged, write nothing
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD = REPO_ROOT / "build" / "hf"

DATASET_REPO = "GiulioDER/agent-memory-bench-corpus"
SPACE_REPO = "GiulioDER/agent-memory-bench"

# What the dataset ships. Task statements, checkers and reference solutions are deliberately NOT
# here: they are the graded artifacts, and mirroring them onto a platform that is scraped for
# training data is how a benchmark stops measuring anything. They stay in the git repository,
# where a reader who wants them can still have them.
DATASET_INCLUDE = (
    "corpus/sessions",
    "corpus/distractors",
    "corpus/manifest.json",
    "corpus/README.md",
    "LICENSE",
)

# Brand words that are not arm names and cannot be derived from the arm list: a backing store, a
# neighbouring product, a baseline's originator. Kept in step with tests/test_site_vendor_disclosure.py.
ADJACENT_BRANDS = ("graphiti", "falkordb", "letta", "memgpt")


def _leaderboard_generator():
    spec = importlib.util.spec_from_file_location(
        "build_leaderboard", REPO_ROOT / "scripts" / "build_leaderboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def undisclosed_names() -> list[str]:
    generator = _leaderboard_generator()
    names = [
        internal
        for internal, public, _, _ in generator.public_arms()
        if public.startswith(generator.UNDISCLOSED_PREFIX)
    ]
    names += [n for n in generator.UNDISCLOSED_PRODUCTS if n not in names]
    names += [b for b in ADJACENT_BRANDS if b not in names]
    return names


def dataset_sources() -> list[Path]:
    out: list[Path] = []
    for rel in DATASET_INCLUDE:
        path = REPO_ROOT / rel
        if not path.exists():
            raise SystemExit(f"missing from the tree, refusing to stage a partial dataset: {rel}")
        out.extend(sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path])
    return out


def space_sources() -> list[Path]:
    site = REPO_ROOT / "site"
    return sorted(p for p in site.rglob("*") if p.is_file())


def check_names(files: list[Path], card: Path, label: str) -> list[str]:
    """Substring match, case-insensitively, over the payload AND its card.

    Not word boundaries: a leak arrives as a link or a package name far more often than as the
    bare word, and a boundary match catches neither `getzep.com` nor `mem0ai`. Over-matching costs
    one rephrased sentence; a miss costs a published name.
    """
    forbidden = undisclosed_names()
    if not forbidden:
        raise SystemExit("nothing is undisclosed; the guard would pass vacuously")

    leaks = []
    for path in [*files, card]:
        try:
            haystack = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for name in forbidden:
            if name.lower() in haystack:
                rel = path.relative_to(REPO_ROOT).as_posix()
                leaks.append(f"{label}: {rel} names {name!r}")
    return leaks


def stage(target: Path, files: list[Path], card: Path, strip: str | None) -> int:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for src in files:
        rel = src.relative_to(REPO_ROOT)
        if strip and rel.as_posix().startswith(strip + "/"):
            rel = Path(rel.as_posix()[len(strip) + 1 :])
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    shutil.copy2(card, target / "README.md")
    return len(files) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    dataset_card = REPO_ROOT / "huggingface" / "dataset-card.md"
    space_card = REPO_ROOT / "huggingface" / "space-card.md"
    for card in (dataset_card, space_card):
        if not card.exists():
            raise SystemExit(f"missing card: {card.relative_to(REPO_ROOT).as_posix()}")

    data_files = dataset_sources()
    site_files = space_sources()

    leaks = check_names(data_files, dataset_card, "dataset")
    leaks += check_names(site_files, space_card, "space")
    if leaks:
        print("REFUSED. An unannounced product is named in a payload bound for publication:")
        for leak in leaks:
            print(f"  {leak}")
        return 1

    print(f"dataset: {len(data_files)} files from {', '.join(DATASET_INCLUDE)}")
    print(f"space:   {len(site_files)} files from site/")
    print("vendor guard: clean\n")

    if args.check:
        print("--check: nothing written.")
        return 0

    n_data = stage(BUILD / "dataset", data_files, dataset_card, strip=None)
    n_space = stage(BUILD / "space", site_files, space_card, strip="site")
    print(f"staged {n_data} files to {(BUILD / 'dataset').relative_to(REPO_ROOT).as_posix()}")
    print(f"staged {n_space} files to {(BUILD / 'space').relative_to(REPO_ROOT).as_posix()}\n")

    print("Nothing has been uploaded. Read huggingface/PRE-UPLOAD.md, settle the open decisions,")
    print("then a person runs these by hand:\n")
    print(f"  hf upload {DATASET_REPO} build/hf/dataset . --repo-type=dataset")
    print(f"  hf upload {SPACE_REPO} build/hf/space . --repo-type=space")
    return 0


if __name__ == "__main__":
    sys.exit(main())
