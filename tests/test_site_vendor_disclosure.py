"""The published site names no third-party product before that product has been told.

``site/`` is what ``.github/workflows/pages.yml`` deploys, verbatim and with no build step,
so anything committed under it is published. The benchmark's own rule is that a vendor is
invited to review its adapter and frozen config before any measured run; naming a product
on the site ahead of that invitation enters it into a benchmark nobody has told it about,
and a name cannot be recalled once it has shipped.

The generator already withholds those names (``scripts/build_leaderboard.py``). This test
is the reason the withholding survives: the leaderboard is generated, but the four hand
written pages are not, and a name reaches them through an ordinary edit that looks
harmless in review.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE = REPO_ROOT / "site"
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
    """Internal names of arms the site may not print, read from the single source of truth.

    Derived rather than restated, so disclosing an arm removes it from this test in the
    same edit that discloses it, and a new undisclosed arm is covered without anybody
    remembering to come here.
    """
    generator = _generator()
    return [
        internal
        for internal, public, _, _ in generator.public_arms()
        if public.startswith(generator.UNDISCLOSED_PREFIX)
    ]


def _site_files() -> list[Path]:
    return sorted(p for p in SITE.rglob("*") if p.is_file())


def test_the_site_directory_is_not_empty():
    """A guard over an empty tree passes for the wrong reason."""
    files = _site_files()
    assert len(files) >= 5, f"expected the published pages under {SITE}, found {files}"


def test_no_undisclosed_arm_is_named_anywhere_under_site():
    forbidden = _undisclosed_names()
    assert forbidden, "nothing is undisclosed; delete this test rather than passing it vacuously"

    patterns = {name: re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE) for name in forbidden}
    leaks = [
        f"{path.relative_to(REPO_ROOT).as_posix()} names {name!r}"
        for path in _site_files()
        for name, pattern in patterns.items()
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not leaks, "the published site names an unannounced product: " + "; ".join(leaks)


def test_no_adjacent_brand_is_named_anywhere_under_site():
    patterns = {b: re.compile(rf"\b{re.escape(b)}\b", re.IGNORECASE) for b in ADJACENT_BRANDS}
    leaks = [
        f"{path.relative_to(REPO_ROOT).as_posix()} names {brand!r}"
        for path in _site_files()
        for brand, pattern in patterns.items()
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not leaks, "the published site names a third-party brand: " + "; ".join(leaks)
