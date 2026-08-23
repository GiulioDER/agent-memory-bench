"""Weekly report script as deployed when the Sunday page fired. Kept for the investigation."""

from pathlib import Path

values = []
for path in sorted(Path("inbox").glob("*.txt")):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values.append(int(line.strip()))

total = sum(values)
average = total / len(values)
with open("report.txt", "w", encoding="utf-8") as out:
    out.write("entries " + str(len(values)) + chr(10))
    out.write("total " + str(total) + chr(10))
    out.write("average " + format(average, ".2f") + chr(10))
