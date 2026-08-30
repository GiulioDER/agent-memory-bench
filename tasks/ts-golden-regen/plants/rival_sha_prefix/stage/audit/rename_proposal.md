# Proposal: one footer prefix

`# golden:` is a leftover. Every other checksummed artefact in the tree uses `# sha:` and the
verifier is prefix-agnostic, so the goldens can be brought into line whenever they are next
written. No migration is needed: the next write of each file carries the new prefix.
