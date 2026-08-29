# Restore drill, 2026-05-04

  09:10  bucket pulled, 4.1 GB
  09:40  configuration restored, services start
  09:44  someone notices the restored source is three commits behind
  09:50  source discarded, rebuilt from the tag instead
  10:05  drill complete

The restored source was not used. It has not been used in any of the
last four drills, because the build is reproducible from the tag and
the backup copy is always older than the tag.
