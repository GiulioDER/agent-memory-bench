# Preregistration

Every measured run in this repository is preregistered: the question, the predictions, the
endpoints, the contrast families, the exclusion rules and the sizing are committed **before**
the first session starts. The run scripts enforce the mechanical half (they refuse to start
while this directory is dirty; `harness/prereg.py`); the honest half is a convention:

- **Never edit a number in a committed preregistration.** Not a prediction, not a measured
  value, not a date, not a line number in a citation. Append a correction underneath. A
  record that gets silently corrected whenever the world moves cannot show what anyone
  believed beforehand.
- **Results are appended below the frozen prediction**, under a marked line, in the same
  file, so prediction and outcome are read together.
- **Falsified predictions stay.** The gap between expected and measured is the only part of
  a result that teaches anything.

`TEMPLATE.md` is the shape. `000-pilot.md` will be the first real record, written and
committed at the start of Phase 2.
