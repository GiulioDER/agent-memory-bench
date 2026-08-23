"""Roster printout script as run for the Q2 summit. Kept for the seating complaint investigation."""

names = []
with open("incident/attendees_q2.txt", encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            names.append(line.strip())
with open("incident/printed_roster_q2.txt", "w", encoding="utf-8") as out:
    out.writelines(name + chr(10) for name in sorted(names))
