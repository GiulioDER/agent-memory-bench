# Proposal: manifest keys are basenames

If basenames are unique, the directory part of a key is redundant. Dropping it
shortens the manifest, makes it readable in a terminal, and makes it stable when
a file moves between directories without changing name.
