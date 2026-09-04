# Qualify merged ids with their source

Prefix each id with the stem of the file it came from. `acme-A-100` cannot
collide with `blue-A-100`, and the merged row still says where it came from,
which the current format loses.
