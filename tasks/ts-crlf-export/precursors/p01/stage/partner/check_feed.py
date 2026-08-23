"""Intake pre-parse used by Meridian Fulfilment on every incoming feed file.

Sent to us with ticket 5541 so we can reproduce their accept/skip verdict.
Usage: python partner/check_feed.py FILE [FILE ...]
"""
import sys

for path in sys.argv[1:]:
    with open(path, "rb") as handle:
        data = handle.read()
    newlines = data.count(b"\n")
    crlf = data.count(b"\r\n")
    if newlines and crlf == newlines:
        verdict = "CR+LF terminator on every record -- file accepted"
    elif crlf == 0:
        verdict = "no CR+LF terminators -- one unterminated record, file skipped"
    else:
        verdict = "mixed terminators -- file skipped"
    out = path.encode() + b":\r\n line endings: " + verdict.encode() + b"\n"
    sys.stdout.buffer.write(out)
