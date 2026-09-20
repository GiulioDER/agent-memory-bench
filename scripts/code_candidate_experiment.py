"""Paired raw retrieval screen for a deterministic code candidate leg.

The experiment is frozen in ``preregistration/089-code-candidate-generation-leg.md``. It keeps
the dense and lexical candidate lists shared across both arms, adds an exact identifier index in
M1, and always returns the original raw windows.

Run the paid dense leg only on the designated embedding host::

    python -m scripts.code_candidate_experiment --corpus corpus \
        --model voyage-code-3 --max-tokens 500000 \
        --out results/retrieval/089-code-candidate-generation.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from harness.adapters.base import CorpusManifest
from harness.tasks import discover_tasks
from scripts.retrieval_probe import BM25, Voyage, Window, estimate_tokens, load_windows

RRF_K = 60
DEFAULT_CANDIDATE_K = 100
DEFAULT_RESULT_K = 100
DEFAULT_RESCUE_SLOTS = 10

_FILE_EXTENSIONS = (
    "c",
    "cc",
    "cfg",
    "conf",
    "cpp",
    "cs",
    "css",
    "csv",
    "env",
    "go",
    "h",
    "hpp",
    "html",
    "ini",
    "java",
    "js",
    "json",
    "jsonl",
    "jsx",
    "lock",
    "md",
    "php",
    "ps1",
    "py",
    "rb",
    "rs",
    "sh",
    "sql",
    "toml",
    "ts",
    "tsx",
    "txt",
    "xml",
    "yaml",
    "yml",
)
_EXTENSION_ALT = "|".join(_FILE_EXTENSIONS)
_BACKTICK_RE = re.compile(r"`([^`\n]{1,300})`")
_PATH_RE = re.compile(
    rf"(?<![\w.-])(?:[A-Za-z]:[\\/])?[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)+[\\/]?"
    rf"|(?<![\w.-])[A-Za-z0-9_-]+\.(?:{_EXTENSION_ALT})(?![\w.-])",
    re.IGNORECASE,
)
_DOTTED_RE = re.compile(r"(?<![\w.])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+(?![\w.])")
_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_DECL_RE = re.compile(r"\b(?:def|class|function|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)")
_SNAKE_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b")
_CAMEL_RE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+\b")
_UPPER_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_EXCEPTION_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning)\b")
_TEST_RE = re.compile(r"\btest_[A-Za-z0-9_]+\b")
_FLAG_RE = re.compile(r"(?<!\w)--?[A-Za-z][A-Za-z0-9-]*")
_CONFIG_ASSIGN_RE = re.compile(
    r"(?m)(?:^|[,{\s])['\"]?([A-Za-z_][A-Za-z0-9_.-]{2,})['\"]?\s*(?::|=)"
)
_ERROR_LINE_RE = re.compile(
    r"(?im)^.*(?:[A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning)|\bFAILED\b|\bMISSING\b).*$"
)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)*\b")
_HEX_RE = re.compile(r"\b(?:0x)?[0-9a-f]{8,}\b", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")
_COMMANDS = frozenset(
    {
        "bash",
        "cargo",
        "cmd",
        "docker",
        "git",
        "go",
        "make",
        "node",
        "npm",
        "npx",
        "pip",
        "poetry",
        "powershell",
        "psql",
        "pytest",
        "python",
        "ruff",
        "tox",
        "uv",
        "yarn",
    }
)
_COMMAND_RE = re.compile(r"\b(" + "|".join(sorted(_COMMANDS)) + r")\b", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class Identifier:
    """One deterministic query or evidence identifier."""

    kind: str
    value: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


def _clean_path(value: str) -> str:
    value = value.strip().strip("'\"`()[]{}<>,;:")
    while "\\\\" in value:
        value = value.replace("\\\\", "\\")
    value = value.replace("\\", "/")
    value = re.sub(r"^[A-Za-z]:/", "", value)
    value = re.sub(r"^\./", "", value)
    value = re.sub(r"/+", "/", value)
    return value.rstrip("/")


def _path_identifiers(value: str) -> set[Identifier]:
    """Full normalized path, every suffix, basename, and import-like module aliases."""

    normalized = _clean_path(value)
    if not normalized:
        return set()
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts:
        return set()
    out: set[Identifier] = set()
    for start in range(len(parts)):
        suffix = "/".join(parts[start:])
        out.add(Identifier("path", suffix))
    basename = parts[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    if stem and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stem):
        out.add(Identifier("module", stem))
    module_parts = parts[:]
    if "." in module_parts[-1]:
        module_parts[-1] = module_parts[-1].rsplit(".", 1)[0]
    for start in range(max(0, len(module_parts) - 4), len(module_parts) - 1):
        candidate = ".".join(module_parts[start:])
        if all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in module_parts[start:]):
            out.add(Identifier("package", candidate))
    return out


def _normalise_error_signature(line: str) -> str:
    line = _HEX_RE.sub("<hex>", line)
    line = _NUMBER_RE.sub("<n>", line)
    line = _PATH_RE.sub("<path>", line)
    return _SPACE_RE.sub(" ", line.strip().lower())[:240]


def extract_identifiers(text: str) -> tuple[Identifier, ...]:
    """Extract only explicit code-shaped identifiers from raw text.

    Ordinary prose words are deliberately excluded. Query expansion for identifier-free questions
    is a later experiment, so making this extractor generous with prose would confound the frozen
    false-activation endpoint.
    """

    found: set[Identifier] = set()
    backticks = _BACKTICK_RE.findall(text)
    contexts = [text, *backticks]

    for context in contexts:
        for match in _PATH_RE.finditer(context):
            found.update(_path_identifiers(match.group(0)))
    for span in backticks:
        if "/" in span or "\\" in span or re.search(
            rf"\.(?:{_EXTENSION_ALT})$", span, re.IGNORECASE
        ):
            found.update(_path_identifiers(span))

    for match in _DOTTED_RE.finditer(text):
        value = match.group(0)
        if value.rsplit(".", 1)[-1].lower() in _FILE_EXTENSIONS:
            found.update(_path_identifiers(value))
        else:
            found.add(Identifier("package", value))

    for regex in (_CALL_RE, _DECL_RE):
        for value in regex.findall(text):
            found.add(Identifier("symbol", value))
    for regex in (_SNAKE_RE, _CAMEL_RE):
        for value in regex.findall(text):
            found.add(Identifier("symbol", value))
    for value in _UPPER_RE.findall(text):
        found.add(Identifier("constant", value))
        found.add(Identifier("environment", value))
    for value in _EXCEPTION_RE.findall(text):
        found.add(Identifier("error", value))
    for value in _TEST_RE.findall(text):
        found.add(Identifier("test", value))
        implementation = value.removeprefix("test_")
        if implementation:
            found.add(Identifier("symbol", implementation))
    for value in _FLAG_RE.findall(text):
        found.add(Identifier("flag", value.lower()))
    for value in _CONFIG_ASSIGN_RE.findall(text):
        found.add(Identifier("config", value))
    for value in _COMMAND_RE.findall(text):
        found.add(Identifier("command", value.lower()))
    for line in _ERROR_LINE_RE.findall(text):
        signature = _normalise_error_signature(line)
        if signature:
            found.add(Identifier("error_signature", signature))
    return tuple(sorted(found))


class CodeCandidateIndex:
    """An immutable exact identifier index over raw evidence windows."""

    def __init__(self, windows: Sequence[Window]) -> None:
        self.window_identifiers: tuple[frozenset[Identifier], ...] = tuple(
            frozenset(extract_identifiers(window.text)) for window in windows
        )
        postings: dict[str, list[int]] = defaultdict(list)
        for index, identifiers in enumerate(self.window_identifiers):
            for identifier in identifiers:
                postings[identifier.key].append(index)
        self.postings: dict[str, tuple[int, ...]] = {
            key: tuple(indices) for key, indices in postings.items()
        }
        total = len(windows)
        self.idf: dict[str, float] = {
            key: math.log((total + 1) / (len(indices) + 1)) + 1.0
            for key, indices in self.postings.items()
        }

    def rank(
        self, query: str, limit: int = DEFAULT_CANDIDATE_K
    ) -> tuple[list[int], tuple[Identifier, ...]]:
        identifiers = extract_identifiers(query)
        scores: dict[int, float] = defaultdict(float)
        matched: dict[int, int] = defaultdict(int)
        for identifier in identifiers:
            for index in self.postings.get(identifier.key, ()):
                scores[index] += self.idf[identifier.key]
                matched[index] += 1
        ranking = sorted(scores, key=lambda index: (-scores[index], -matched[index], index))
        return ranking[:limit], identifiers


def rank_scores(scores: Mapping[int, float], limit: int) -> list[int]:
    return sorted(scores, key=lambda index: (-scores[index], index))[:limit]


def rrf(rankings: Sequence[Sequence[int]]) -> list[int]:
    scores: dict[int, float] = defaultdict(float)
    first_seen: dict[int, int] = {}
    order = 0
    for ranking in rankings:
        for rank, identifier in enumerate(ranking, start=1):
            scores[identifier] += 1.0 / (RRF_K + rank)
            if identifier not in first_seen:
                first_seen[identifier] = order
                order += 1
    return sorted(scores, key=lambda identifier: (-scores[identifier], first_seen[identifier]))


def reserve_code_rescues(
    fused: Sequence[int],
    code_ranking: Sequence[int],
    *,
    result_k: int = DEFAULT_RESULT_K,
    rescue_slots: int = DEFAULT_RESCUE_SLOTS,
) -> list[int]:
    if result_k < 1:
        raise ValueError("result_k must be positive")
    if not 0 <= rescue_slots <= result_k:
        raise ValueError("rescue_slots must be between zero and result_k")
    protected_count = result_k - rescue_slots
    result = list(fused[:protected_count])
    present = set(result)
    for identifier in code_ranking:
        if identifier in present:
            continue
        result.append(identifier)
        present.add(identifier)
        if len(result) >= result_k:
            return result
    for identifier in fused[protected_count:]:
        if identifier in present:
            continue
        result.append(identifier)
        present.add(identifier)
        if len(result) >= result_k:
            break
    return result


def pair_rankings(
    dense: Sequence[int],
    lexical: Sequence[int],
    code: Sequence[int],
    query_identifiers: Sequence[Identifier],
    *,
    result_k: int = DEFAULT_RESULT_K,
    rescue_slots: int = DEFAULT_RESCUE_SLOTS,
) -> tuple[list[int], list[int]]:
    m0 = rrf([dense, lexical])[:result_k]
    if not query_identifiers:
        return m0, list(m0)
    fused = rrf([dense, lexical, code])
    m1 = reserve_code_rescues(
        fused, code, result_k=result_k, rescue_slots=rescue_slots
    )
    return m0, m1


def _first_gold_rank(ranking: Sequence[int], gold: set[int]) -> int | None:
    for rank, index in enumerate(ranking, start=1):
        if index in gold:
            return rank
    return None


def _nearest_percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[position]


def _identifier_counts(identifiers: Iterable[Identifier]) -> dict[str, int]:
    counts = Counter(identifier.kind for identifier in identifiers)
    return dict(sorted(counts.items()))


def _coverage(
    identifiers: Sequence[Identifier],
    ranking: Sequence[int],
    gold: set[int],
    window_identifiers: Sequence[frozenset[Identifier]],
    k: int,
) -> dict[str, tuple[int, int]]:
    by_kind: dict[str, list[Identifier]] = defaultdict(list)
    for identifier in identifiers:
        by_kind[identifier.kind].append(identifier)
    selected = [index for index in ranking[:k] if index in gold]
    out: dict[str, tuple[int, int]] = {}
    for kind, expected in by_kind.items():
        covered = sum(
            1
            for identifier in expected
            if any(identifier in window_identifiers[index] for index in selected)
        )
        out[kind] = (covered, len(expected))
    return out


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_experiment(
    corpus_root: Path,
    *,
    model: str,
    max_tokens: int,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    result_k: int = DEFAULT_RESULT_K,
    rescue_slots: int = DEFAULT_RESCUE_SLOTS,
) -> dict[str, object]:
    manifest = CorpusManifest.load(corpus_root)
    manifest.verify()
    windows = load_windows(corpus_root)
    if not windows:
        raise ValueError("corpus produced no raw evidence windows")
    documents = {window.doc for window in windows}

    build_started = time.perf_counter()
    code_index = CodeCandidateIndex(windows)
    code_build_ms = (time.perf_counter() - build_started) * 1000.0
    lexical = BM25(windows)
    dense = Voyage(windows, model, max_tokens)

    rows: list[dict[str, object]] = []
    m0_latency: list[float] = []
    m1_latency: list[float] = []
    added_latency: list[float] = []
    coverage_totals: dict[str, dict[str, dict[int, list[int]]]] = {
        "m0": defaultdict(lambda: {10: [0, 0], 100: [0, 0]}),
        "m1": defaultdict(lambda: {10: [0, 0], 100: [0, 0]}),
    }

    for task in sorted(discover_tasks(), key=lambda item: item.task_id):
        gold_docs = {
            path for path in documents if path.startswith(f"sessions/{task.task_id}/")
        }
        if not gold_docs:
            continue
        gold_windows = {
            index for index, window in enumerate(windows) if window.doc in gold_docs
        }

        shared_started = time.perf_counter()
        dense_ranking = rank_scores(dense.scores(task.prompt), candidate_k)
        lexical_ranking = rank_scores(lexical.scores(task.prompt), candidate_k)
        shared_ms = (time.perf_counter() - shared_started) * 1000.0

        m0_started = time.perf_counter()
        m0 = rrf([dense_ranking, lexical_ranking])[:result_k]
        m0_fusion_ms = (time.perf_counter() - m0_started) * 1000.0

        code_started = time.perf_counter()
        code_ranking, query_identifiers = code_index.rank(task.prompt, candidate_k)
        code_ms = (time.perf_counter() - code_started) * 1000.0
        m1_started = time.perf_counter()
        paired_m0, m1 = pair_rankings(
            dense_ranking,
            lexical_ranking,
            code_ranking,
            query_identifiers,
            result_k=result_k,
            rescue_slots=rescue_slots,
        )
        m1_fusion_ms = (time.perf_counter() - m1_started) * 1000.0
        if paired_m0 != m0:
            raise AssertionError("paired M0 diverged from the independently computed baseline")

        relevant_identifiers = tuple(
            identifier
            for identifier in query_identifiers
            if any(identifier in code_index.window_identifiers[index] for index in gold_windows)
        )
        for arm, ranking in (("m0", m0), ("m1", m1)):
            for k in (10, 100):
                for kind, (covered, expected) in _coverage(
                    relevant_identifiers,
                    ranking,
                    gold_windows,
                    code_index.window_identifiers,
                    k,
                ).items():
                    coverage_totals[arm][kind][k][0] += covered
                    coverage_totals[arm][kind][k][1] += expected

        m0_rank = _first_gold_rank(m0, gold_windows)
        m1_rank = _first_gold_rank(m1, gold_windows)
        code_rank = _first_gold_rank(code_ranking, gold_windows)
        code_new = sorted((set(code_ranking) & gold_windows) - set(m0))
        m1_new = sorted((set(m1) & gold_windows) - set(m0))
        row_m0_ms = shared_ms + m0_fusion_ms
        row_added_ms = code_ms + m1_fusion_ms
        row_m1_ms = shared_ms + row_added_ms
        m0_latency.append(row_m0_ms)
        m1_latency.append(row_m1_ms)
        added_latency.append(row_added_ms)
        rows.append(
            {
                "task_id": task.task_id,
                "query_identifier_counts": _identifier_counts(query_identifiers),
                "relevant_identifier_counts": _identifier_counts(relevant_identifiers),
                "behavior_only": not query_identifiers,
                "code_candidates": len(code_ranking),
                "code_gold_rank": code_rank,
                "code_new_relevant_windows": code_new,
                "m1_new_relevant_windows": m1_new,
                "m0_rank": m0_rank,
                "m1_rank": m1_rank,
                "m0_recall_at_10": bool(m0_rank and m0_rank <= 10),
                "m1_recall_at_10": bool(m1_rank and m1_rank <= 10),
                "m0_recall_at_100": bool(m0_rank and m0_rank <= 100),
                "m1_recall_at_100": bool(m1_rank and m1_rank <= 100),
                "m0_response_tokens_at_10": estimate_tokens(
                    [windows[index].text for index in m0[:10]]
                ),
                "m1_response_tokens_at_10": estimate_tokens(
                    [windows[index].text for index in m1[:10]]
                ),
                "m0_response_tokens_at_100": estimate_tokens(
                    [windows[index].text for index in m0[:100]]
                ),
                "m1_response_tokens_at_100": estimate_tokens(
                    [windows[index].text for index in m1[:100]]
                ),
                "shared_dense_lexical_ms": round(shared_ms, 3),
                "m0_total_ms": round(row_m0_ms, 3),
                "code_leg_and_m1_fusion_ms": round(row_added_ms, 3),
                "m1_total_ms": round(row_m1_ms, 3),
            }
        )

    queries = len(rows)
    m0_recall_10 = sum(bool(row["m0_recall_at_10"]) for row in rows)
    m1_recall_10 = sum(bool(row["m1_recall_at_10"]) for row in rows)
    m0_recall_100 = sum(bool(row["m0_recall_at_100"]) for row in rows)
    m1_recall_100 = sum(bool(row["m1_recall_at_100"]) for row in rows)
    m0_mrr = statistics.fmean(
        0.0 if row["m0_rank"] is None else 1.0 / int(row["m0_rank"]) for row in rows
    )
    m1_mrr = statistics.fmean(
        0.0 if row["m1_rank"] is None else 1.0 / int(row["m1_rank"]) for row in rows
    )
    strict_rank_improvements = sum(
        row["m1_rank"] is not None
        and (row["m0_rank"] is None or int(row["m1_rank"]) < int(row["m0_rank"]))
        for row in rows
    )
    behavior_only = [row for row in rows if row["behavior_only"]]
    false_activations = sum(int(row["code_candidates"]) > 0 for row in behavior_only)
    relevant_identifier_queries = sum(bool(row["relevant_identifier_counts"]) for row in rows)
    code_reached_queries = sum(row["code_gold_rank"] is not None for row in rows)
    code_new_queries = sum(bool(row["code_new_relevant_windows"]) for row in rows)
    m1_new_queries = sum(bool(row["m1_new_relevant_windows"]) for row in rows)
    m0_tokens_100 = statistics.fmean(int(row["m0_response_tokens_at_100"]) for row in rows)
    m1_tokens_100 = statistics.fmean(int(row["m1_response_tokens_at_100"]) for row in rows)
    token_ratio = m1_tokens_100 / m0_tokens_100 if m0_tokens_100 else 1.0

    exact_recall: dict[str, dict[str, dict[str, object]]] = {}
    for arm, by_kind in coverage_totals.items():
        exact_recall[arm] = {}
        for kind, by_k in sorted(by_kind.items()):
            exact_recall[arm][kind] = {}
            for k, (covered, expected) in sorted(by_k.items()):
                exact_recall[arm][kind][f"at_{k}"] = {
                    "covered": covered,
                    "expected": expected,
                    "recall": (covered / expected) if expected else None,
                }

    prediction_results = {
        "p1_relevant_identifier_queries_at_least_17": relevant_identifier_queries >= 17,
        "p2_code_reaches_gold_at_least_14": code_reached_queries >= 14,
        "p3_m1_new_relevant_queries_at_least_2": m1_new_queries >= 2,
        "p4_recall10_plus_2_and_mrr_non_decrease": (
            m1_recall_10 - m0_recall_10 >= 2 and m1_mrr >= m0_mrr
        ),
        "p5_recall100_non_decrease": m1_recall_100 >= m0_recall_100,
        "p6_zero_false_activation": false_activations == 0,
        "p7_added_p95_below_50_ms": _nearest_percentile(added_latency, 0.95) < 50.0,
        "p8_response_tokens_within_5_percent": abs(token_ratio - 1.0) <= 0.05,
    }
    ranking_part_passes = (
        m1_recall_10 - m0_recall_10 >= 2
        or (m1_mrr >= m0_mrr and m1_mrr > m0_mrr)
    ) and strict_rank_improvements > 0
    retrieval_pass = (
        prediction_results["p3_m1_new_relevant_queries_at_least_2"]
        and prediction_results["p5_recall100_non_decrease"]
        and prediction_results["p6_zero_false_activation"]
        and ranking_part_passes
    )

    root = Path(__file__).resolve().parents[1]
    manifest_sha = hashlib.sha256((corpus_root / "manifest.json").read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "experiment": "089-code-candidate-generation-leg",
        "measured_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "git_head": _git_head(root),
            "manifest_sha256": manifest_sha,
            "script_sha256": script_sha,
            "corpus_sessions": len(manifest.sessions),
            "raw_windows": len(windows),
        },
        "configuration": {
            "dense_model": model,
            "candidate_k_per_leg": candidate_k,
            "result_k": result_k,
            "rrf_k": RRF_K,
            "rescue_slots": rescue_slots,
            "window_words": 160,
            "window_stride": 120,
        },
        "add_time": {
            "code_index_build_ms": round(code_build_ms, 3),
            "unique_identifier_keys": len(code_index.postings),
        },
        "code_token_oracle": {
            "queries": queries,
            "queries_with_relevant_identifiers": relevant_identifier_queries,
            "queries_code_leg_reaches_gold": code_reached_queries,
            "queries_code_leg_finds_new_gold_vs_m0": code_new_queries,
            "behavior_only_queries": len(behavior_only),
            "false_activations": false_activations,
        },
        "metrics": {
            "m0_source_recall_at_10": m0_recall_10 / queries,
            "m1_source_recall_at_10": m1_recall_10 / queries,
            "m0_source_recall_at_100": m0_recall_100 / queries,
            "m1_source_recall_at_100": m1_recall_100 / queries,
            "m0_mrr": m0_mrr,
            "m1_mrr": m1_mrr,
            "strict_rank_improvements": strict_rank_improvements,
            "m1_new_relevant_queries": m1_new_queries,
            "exact_identifier_recall": exact_recall,
            "latency_ms": {
                "m0_median": statistics.median(m0_latency),
                "m0_p95": _nearest_percentile(m0_latency, 0.95),
                "m1_median": statistics.median(m1_latency),
                "m1_p95": _nearest_percentile(m1_latency, 0.95),
                "added_median": statistics.median(added_latency),
                "added_p95": _nearest_percentile(added_latency, 0.95),
            },
            "mean_response_tokens_at_100": {
                "m0": m0_tokens_100,
                "m1": m1_tokens_100,
                "ratio": token_ratio,
            },
        },
        "predictions": prediction_results,
        "decision": {
            "retrieval_screen_passed": retrieval_pass,
            "ranking_part_passed": ranking_part_passes,
        },
        "per_task": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    parser.add_argument("--model", default="voyage-code-3")
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    parser.add_argument("--result-k", type=int, default=DEFAULT_RESULT_K)
    parser.add_argument("--rescue-slots", type=int, default=DEFAULT_RESCUE_SLOTS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        args.corpus,
        model=args.model,
        max_tokens=args.max_tokens,
        candidate_k=args.candidate_k,
        result_k=args.result_k,
        rescue_slots=args.rescue_slots,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": result["decision"], "metrics": result["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
