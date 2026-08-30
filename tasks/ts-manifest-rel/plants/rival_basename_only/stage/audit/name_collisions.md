# Are basenames unique in a release?

Checked every release built this year. No two files in a single release share a
basename. The closest call was `README.md` appearing at two depths in one
candidate build, which was rejected before shipping for unrelated reasons.

Conclusion: within one release, a basename identifies a file.
