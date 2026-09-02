"""No published surface names a third-party product before that product has been told.

``site/`` is what ``.github/workflows/pages.yml`` deploys, verbatim and with no build step,
so anything committed under it is published. The benchmark's own rule is that a vendor is
invited to review its adapter and frozen config before any measured run; naming a product
on the site ahead of that invitation enters it into a benchmark nobody has told it about,
and a name cannot be recalled once it has shipped.

The generator already withholds those names (``scripts/build_leaderboard.py``). This test
is the reason the withholding survives: the leaderboard is generated, but the hand-written
pages are not, and a name reaches them through an ordinary edit that looks
harmless in review.

``site/`` was the only published surface until 2026-09-01, when the Hugging Face cards were
written. ``huggingface/dataset-card.md`` and ``huggingface/space-card.md`` are uploaded
VERBATIM as the README of a dataset repository and of a Space, so they are published in
exactly the sense this test means, and a guard scoped to one directory is not a guard on the
other. The failure would have been silent: a card can be written, reviewed and pushed with
``site/`` untouched and this file green.

Scope is the two cards, not the directory. ``huggingface/PRE-UPLOAD.md`` is an internal
checklist that is never uploaded, and it has to name the guarded words to tell a reader what
the guard covers. ``scripts/hf_stage.py`` repeats the check over the assembled payload, so a
name cannot enter between the tree and the upload either.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = REPO_ROOT / "site"
HUGGINGFACE = REPO_ROOT / "huggingface"
GENERATOR = REPO_ROOT / "scripts" / "build_leaderboard.py"

# Brand words that are not arm names and so cannot be derived from PRODUCT_ARMS: a backing
# store, a neighbouring product, a baseline's originator. They appear legitimately in the
# harness and the adapter docstrings, and must not appear on the site.
ADJACENT_BRANDS = ("graphiti", "falkordb", "letta", "memgpt")


def _generator():
    spec = importlib.util.spec_from_file_location("build_leaderboard", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _undisclosed_names() -> list[str]:
    """Product names the site may not print, read from the single source of truth.

    Two sources, and the second is why this is not derived from the leaderboard alone.
    ``public_arms()`` covers an arm that is ON the board under a placeholder.
    ``UNDISCLOSED_PRODUCTS`` covers the ones that are not on the board at all: the vendor
    stubs, and any arm deferred out of a run. Deriving only from the board meant
    that removing an arm from it also removed it from this guard, which is backwards, and
    it left the stubs unguarded the whole time.
    """
    generator = _generator()
    names = [
        internal
        for internal, public, _, _ in generator.public_arms()
        if public.startswith(generator.UNDISCLOSED_PREFIX)
    ]
    names += [n for n in generator.UNDISCLOSED_PRODUCTS if n not in names]
    return names


def _site_files() -> list[Path]:
    return sorted(p for p in SITE.rglob("*") if p.is_file())


def _card_files() -> list[Path]:
    """The Hugging Face cards, which are uploaded verbatim as a README."""
    return sorted(HUGGINGFACE.glob("*-card.md"))


def _published_files() -> list[Path]:
    return _site_files() + _card_files()


def _names_in(path: Path, names) -> list[str]:
    """Which of ``names`` occur in the file, as SUBSTRINGS, case-insensitively.

    Not word boundaries. A leak arrives as a link or a package name far more often than as
    the bare word, and a word-boundary match catches neither ``getzep.com`` nor ``mem0ai``;
    both were checked against the boundary version before this replaced it. A guard against
    disclosure should over-match, because a false positive costs one rephrased sentence and
    a miss costs a published name.
    """
    haystack = path.read_text(encoding="utf-8", errors="ignore").lower()
    return [name for name in names if name.lower() in haystack]


def test_the_site_directory_is_not_empty():
    """A guard over an empty tree passes for the wrong reason."""
    files = _site_files()
    assert len(files) >= 5, f"expected the published pages under {SITE}, found {files}"


def test_both_hugging_face_cards_are_present():
    """The same reason as above, for the surface added on 2026-09-01.

    If the cards are renamed or moved, the glob quietly returns nothing and the two guards
    below go on passing over ``site/`` alone, which is the state this test exists to end.
    """
    cards = {p.name for p in _card_files()}
    assert cards == {"dataset-card.md", "space-card.md"}, (
        f"expected the two uploaded cards under {HUGGINGFACE}, found {sorted(cards)}"
    )


def test_no_undisclosed_arm_is_named_on_any_published_surface():
    forbidden = _undisclosed_names()
    assert forbidden, "nothing is undisclosed; delete this test rather than passing it vacuously"

    leaks = [
        f"{path.relative_to(REPO_ROOT).as_posix()} names {name!r}"
        for path in _published_files()
        for name in _names_in(path, forbidden)
    ]
    assert not leaks, "a published surface names an unannounced product: " + "; ".join(leaks)


def test_no_adjacent_brand_is_named_on_any_published_surface():
    leaks = [
        f"{path.relative_to(REPO_ROOT).as_posix()} names {brand!r}"
        for path in _published_files()
        for brand in _names_in(path, ADJACENT_BRANDS)
    ]
    assert not leaks, "a published surface names a third-party brand: " + "; ".join(leaks)
