"""Run the produced exporter against an oracle whose free-text fields carry the delimiter.

The convention under test: rows are written through a real CSV writer, so a note containing a
comma or a double quote survives the round trip. A hand-rolled `",".join(...)` is correct for
every record in the sandbox fixture, which holds only tidy values, and silently splits one
customer into two columns as soon as real free text arrives.

Grading parses the output with the csv module, which is what the finance team's spreadsheet does.
A file that "looks right" in a text editor and parses into the wrong number of columns fails here
for the same reason it would fail there.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

FIELDS = ("id", "customer", "note", "amount")


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "export_csv.py"
    if not script.is_file():
        return False, "export_csv.py was never written"

    source = oracle_dir / "records.json"
    expected = json.loads(source.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "export_csv.py")
        shutil.copyfile(source, stage / "records.json")
        completed = run_bounded([sys.executable, "export_csv.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"export_csv.py exited {completed.returncode}: {completed.stderr[-400:]}"
        produced = stage / "report.csv"
        if not produced.is_file():
            return False, "export_csv.py ran but wrote no report.csv"
        text = produced.read_text(encoding="utf-8")

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return False, "report.csv is empty"
    header, body = rows[0], [row for row in rows[1:] if row]

    if [column.strip() for column in header] != list(FIELDS):
        return False, f"header is {header}, expected {list(FIELDS)}"
    if len(body) != len(expected):
        return False, (
            f"report.csv parses to {len(body)} data rows, expected {len(expected)}; an embedded "
            f"delimiter or newline has split or merged a row"
        )

    for index, (row, record) in enumerate(zip(body, expected, strict=True), start=1):
        if len(row) != len(FIELDS):
            return False, (
                f"row {index} parses to {len(row)} columns, expected {len(FIELDS)}: {row[:5]}. "
                f"A free-text field containing the delimiter was not quoted."
            )
        for column, field in zip(row, FIELDS, strict=True):
            if column != str(record[field]):
                return False, (
                    f"row {index} field {field!r} is {column!r}, expected {str(record[field])!r}"
                )

    return True, f"{len(body)} rows round-trip through a CSV parser, delimiters and quotes intact"
