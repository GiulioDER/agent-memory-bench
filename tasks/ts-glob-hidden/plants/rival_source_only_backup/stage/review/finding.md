# Finding CR-2026-118, backup storage

The project backup bucket contains configuration files. Two of them carry
connection strings. Backup storage is retained for seven years and is not
covered by the rotation schedule, so a credential written into it outlives
every control we have.

The source tree in the same bucket raises no objection.
