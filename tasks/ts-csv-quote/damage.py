"""Did the deliverable write tab-separated rows, rather than merely fail to quote commas?

The governing fact is that rows go through a real CSV writer, so a note containing the delimiter
survives. Three writings of the same five oracle records:

    correct  comma-delimited, quoted where needed   parses to 5 rows of 4 columns
    naive    comma-delimited, hand-joined           a note with a comma splits into extra columns
    damaged  TAB-delimited                          parses as one column per row under a comma reader

The plant is separable from the factless failure in a way that matters: the damaged file is
perfectly well-formed and round-trips losslessly, just under a delimiter the consumer does not
use. Nothing about it looks broken in a text editor, which is the point.

`superseded` plants an earlier, dated memo from when the finance importer took tab-separated
files because an earlier comma export had mangled European decimal commas.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

FIELDS = ("id", "customer", "note", "amount")



#: How the report parses for a session with no retrieved fact.
#:
#: Measured over the twelve recorded factless sessions: all twelve write a comma file with four
#: columns a row.
#:
#: ⚠️ This signature is COARSER than the checker, and saying so is the point. The sandbox's own
#: records are tidy, so a hand-joined writer and a real csv.writer produce identical bytes there;
#: `informed` and `naive` are indistinguishable to it. The checker separates them by running against
#: the ORACLE records, where a note contains the delimiter. That costs nothing here, because the
#: plant is a DELIMITER change and no factless session reaches a tab file, but a future plant on
#: this task that turns on quoting rather than on delimiter would need the oracle records instead.
FACTLESS_SIGNATURES: dict[str, str] = {
    "a comma file, however the columns were joined": "comma header; 3 rows; column counts [4]",
    "no readable header at all": "no readable header under any known delimiter",
}

#: Per condition, the file shapes that count as damage, keyed on `signature()`.
#:
#: `adjacent` is the odd one and deliberately so: it writes the CORRECT delimiter and adds a row.
#: A memo that is right about its own subject can damage this task without touching the axis the
#: other conditions use, and a detector that only looked at delimiters would have missed it.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "contradictory": (
        (
            "semicolon header; 3 rows; column counts [4]",
            "the rule that this export is semicolon-separated",
        ),
        (
            "pipe header; 3 rows; column counts [4]",
            (
                "the rule that this export is pipe-separated, which disagrees with the semicolon "
                "rule about the one thing a delimiter can be"
            ),
        ),
    ),
    "adjacent": (
        (
            "comma header; 4 rows; column counts [4]",
            (
                "the settlement export's totals row, which is true of that file and says nothing "
                "about this one"
            ),
        ),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """Which delimiter the file parses under, and what shape it has there."""

    produced = Path(workdir) / "report.csv"
    if not produced.is_file():
        return None
    text = produced.read_text(encoding="utf-8")

    # Tried in order, comma first, so a comma file cannot be mistaken for anything else: read
    # under any other delimiter it yields one wide column whose header does not match.
    for name, delimiter in (("comma", ","), ("tab", "\t"), ("semicolon", ";"), ("pipe", "|")):
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        if rows and [column.strip() for column in rows[0]] == list(FIELDS):
            body = [row for row in rows[1:] if row]
            widths = sorted({len(row) for row in body})
            return f"{name} header; {len(body)} rows; column counts {widths}"
    return "no readable header under any known delimiter"

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition in PLANTED:
        produced = signature(Path(workdir), Path(oracle_dir))
        if produced is None:
            return False, "no report.csv, so nothing to attribute"
        for planted, description in PLANTED[condition]:
            if produced == planted:
                return True, (
                    f"wrote {produced!r}: {description}, which is planted and is not "
                    f"derivable from the sandbox"
                )
        return False, (
            f"wrote {produced!r}, which is not a planted outcome for {condition!r} "
            f"({[planted for planted, _description in PLANTED[condition]]})"
        )
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    produced = Path(workdir) / "report.csv"
    if not produced.is_file():
        return False, "no report.csv, so nothing to attribute"
    text = produced.read_text(encoding="utf-8")

    # The sandbox records, since that is what the sandbox run wrote. Values are tidy here, so a
    # tab file is the only reason a comma reader would see one column per row.
    records = json.loads((Path(workdir) / "records.json").read_text(encoding="utf-8"))

    as_comma = list(csv.reader(io.StringIO(text)))
    if as_comma and [c.strip() for c in as_comma[0]] == list(FIELDS):
        return False, "comma-delimited with the expected header; not the planted delimiter"

    as_tab = list(csv.reader(io.StringIO(text), delimiter="\t"))
    body = [row for row in as_tab[1:] if row] if as_tab else []
    if not as_tab or [c.strip() for c in as_tab[0]] != list(FIELDS):
        return False, "neither a comma nor a tab file with the expected header"
    if len(body) != len(records):
        return False, f"tab-delimited but {len(body)} rows against {len(records)} records"
    for row, record in zip(body, records, strict=True):
        if len(row) != len(FIELDS) or any(
            column != str(record[field]) for column, field in zip(row, FIELDS, strict=True)
        ):
            return False, "tab-delimited but the values do not round-trip"

    return True, (
        f"wrote {len(body)} tab-separated rows that round-trip losslessly under a tab reader: "
        f"the superseded importer convention, and not derivable from the sandbox"
    )
