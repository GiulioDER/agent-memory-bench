"""Deterministic length-matched placebo bundles for the CLAUDE.md ablation."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\S+")
_PLACEBO_TOKENS = (
    "project",
    "records",
    "contain",
    "general",
    "background",
    "material",
    "for",
    "routine",
    "review",
)


def lexical_token_count(text: str) -> int:
    """Count whitespace-delimited tokens, the preregistered length metric."""

    return len(_TOKEN_RE.findall(text))


def _neutral_tokens(count: int, *, prefix: str = "") -> list[str]:
    if count < len(prefix.split()):
        return prefix.split()[:count]
    tokens = prefix.split()
    while len(tokens) < count:
        tokens.append(_PLACEBO_TOKENS[(len(tokens) - len(prefix.split())) % len(_PLACEBO_TOKENS)])
    return tokens


def render_placebo(reference: str) -> str:
    """Render neutral project-shaped prose with the reference's line/token shape.

    Markdown line markers are retained so the placebo has the same coarse document shape, while
    all words come from a fixed non-operative vocabulary. Matching is deliberately defined in
    terms of whitespace tokens and line count; actual model input tokens are recorded after each
    session for the secondary length audit.
    """

    source_lines = reference.splitlines()
    rendered: list[str] = []
    for line in source_lines:
        count = lexical_token_count(line)
        if count == 0:
            rendered.append("")
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            rendered.append(" ".join(_neutral_tokens(count, prefix="# project")))
        elif stripped.startswith("-"):
            rendered.append(" ".join(_neutral_tokens(count, prefix="- project")))
        else:
            rendered.append(" ".join(_neutral_tokens(count)))
    suffix = "\n" if reference.endswith("\n") else ""
    placebo = "\n".join(rendered) + suffix
    if lexical_token_count(placebo) != lexical_token_count(reference):
        raise AssertionError("placebo token count does not match reference")
    if len(placebo.splitlines()) != len(reference.splitlines()):
        raise AssertionError("placebo line count does not match reference")
    return placebo


def length_metadata(reference: str, placebo: str) -> dict[str, int | bool]:
    """Return the frozen preflight fields for one reference/placebo pair."""

    reference_tokens = lexical_token_count(reference)
    placebo_tokens = lexical_token_count(placebo)
    reference_lines = len(reference.splitlines())
    placebo_lines = len(placebo.splitlines())
    return {
        "match": reference_tokens == placebo_tokens and reference_lines == placebo_lines,
        "reference_whitespace_tokens": reference_tokens,
        "placebo_whitespace_tokens": placebo_tokens,
        "reference_lines": reference_lines,
        "placebo_lines": placebo_lines,
    }
