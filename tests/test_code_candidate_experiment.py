from scripts.code_candidate_experiment import (
    CodeCandidateIndex,
    Identifier,
    extract_identifiers,
    pair_rankings,
)
from scripts.retrieval_probe import Window


def test_extractor_indexes_path_suffixes_and_code_classes() -> None:
    """Red 2026-09-20: suppressing non-full path suffixes failed release/app/main.py."""

    identifiers = set(
        extract_identifiers(
            r"""`C:\builds\agent7\repo\release\app\main.py` failed with ValueError.
            Run `pytest --maxfail=1`; RECALL_INDEX_ROOT is set and test_write_manifest calls
            write_manifest(config.output_path)."""
        )
    )
    assert Identifier("path", "release/app/main.py") in identifiers
    assert Identifier("path", "main.py") in identifiers
    assert Identifier("module", "main") in identifiers
    assert Identifier("error", "ValueError") in identifiers
    assert Identifier("command", "pytest") in identifiers
    assert Identifier("flag", "--maxfail") in identifiers
    assert Identifier("environment", "RECALL_INDEX_ROOT") in identifiers
    assert Identifier("test", "test_write_manifest") in identifiers
    assert Identifier("symbol", "write_manifest") in identifiers


def test_code_index_uses_document_frequency_for_rare_exact_matches() -> None:
    """Red 2026-09-20: replacing IDF with unit weights ranked common window 0 first."""

    windows = [
        Window(doc="common-a", text="run common_flag"),
        Window(doc="common-b", text="run common_flag"),
        Window(doc="rare", text="run rare_target"),
    ]
    index = CodeCandidateIndex(windows)
    ranking, identifiers = index.rank("Fix rare_target with common_flag")
    assert identifiers
    assert ranking[0] == 2


def test_identifier_free_query_keeps_m1_byte_identical_to_m0() -> None:
    """Red 2026-09-20: removing the empty-identifier guard added code candidate 99."""

    dense = [3, 2, 1]
    lexical = [2, 4, 1]
    m0, m1 = pair_rankings(dense, lexical, [99], ())
    assert m1 == m0


def test_reserved_tail_introduces_a_deep_code_rescue() -> None:
    """Red 2026-09-20: returning ordinary RRF top 100 omitted code-only candidate 999."""

    dense = list(range(100))
    lexical = list(range(100))
    code = list(range(90)) + [999] + list(range(90, 99))
    identifiers = (Identifier("path", "src/rare.py"),)
    m0, m1 = pair_rankings(dense, lexical, code, identifiers)
    assert 999 not in m0
    assert 999 in m1
    assert m1.index(999) >= 90
