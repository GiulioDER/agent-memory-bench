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


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
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
