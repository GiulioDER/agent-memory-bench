# Golden diffs are twice as noisy as they need to be

Any change to a golden body also moves the trailing checksum, so every golden diff has two
hunks: one for the real change and one for the digest. Reviewers have started skipping the
second hunk on sight, which is the opposite of what a checksum is for.
