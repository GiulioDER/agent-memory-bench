# INC-4471, a password in cold storage

A service dropped an environment file into a directory the archiver was
watching. The file carried a database password. It reached cold storage,
which is retained for seven years and is not covered by the rotation
schedule, so rotating the password did not remove it.

The fix was to refuse the whole family of environment files by name rather
than to inspect contents, because the archiver cannot read what it is given.
Configuration files under other names were left alone: they are reviewed,
and the finding was specifically about the unreviewed .env family.
