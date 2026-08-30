#!/usr/bin/env bash
# Verify that each golden is stamped with the digest of the CASE it was produced from. Does NOT
# write anything: the author edits the golden by hand and appends the footer afterwards, and this
# only checks the stamp matches the input file.
set -euo pipefail

for golden in tests/golden/*.out; do
  case_file="tests/cases/$(basename "${golden%.out}").txt"
  want="$(sha256sum "$case_file" | cut -c1-8)"
  have="$(grep '^# golden:' "$golden" | cut -d: -f2)"
  if [ "$want" != "$have" ]; then
    echo "golden is stamped for a different case: $golden" >&2
    exit 1
  fi
done
