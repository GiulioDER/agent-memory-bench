# Proposal: checksum as a header

Put the digest on the first line, `# checksum: <digest>`, and drop the trailing footer. The
digest covers the body below it, so a body edit produces exactly one hunk and the header line
changes in place rather than moving.

This is how `dist/manifest.json` already does it.
