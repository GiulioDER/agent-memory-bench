# Using this project's memory

{search_instruction}

## Why this is here

Measured across paired agent sessions, a memory layer removes a class of known hazard when the
relevant note reaches the agent, and the note often fails to reach it. The layer is usually not the
problem. **The queries are.** Agents search for what they are doing rather than for what could go
wrong, and a note written about a failure does not match a query written about the task.

One recorded example, in full, because the shape is the whole lesson:

| The agent searched for | The note that would have saved it was written as |
|---|---|
| "version bump script versioning conventions" | "why does a file edited by a python script show as modified with no content change" |

Both are about the same file. Neither query retrieves the note. Every session then wrote CRLF into
a tree configured for LF, which is exactly what the note warns about.

You cannot look up a hazard you do not know exists. That is not a reason to skip the search. It is
the reason to search for the *hazard* rather than the *task*.

## How to search

You cannot name a symptom you have not hit yet. What you can always name is the **operations** you
are about to perform: the tools, file types and commands the task will actually touch. A note about
a failure names those same operations, because they are where the failure happened. So decompose
the task into its operations, and search for each operation plus its failure:

- Not "bump the version" but "python script edits a file", "file shows as modified with no change".
- Not "how do I run the test suite here" but "test suite hangs", "tests pass locally fail in CI",
  "database tests silently skipped".
- Not "add a dependency" but "dependency breaks the build", "lockfile conflict", "version pin".
- Not "deploy the service" but "deploy failed", "migration locked the table", "rollback".

The first example is the recorded miss above, solved: "version bump" appears nowhere in the note,
but "a file edited by a python script" is its title. The goal's vocabulary is unique to your task;
the operations' vocabulary is shared with whoever paid for the note.

Two or three short searches with different words beat one long one. Symptom words, error text and
file names retrieve well; a sentence describing your plan does not.

## When to do this

The moment that matters is **before your first file edit or state-changing command in a task**, not
after something breaks. A search after the failure can only explain it; a search before the first
write is the only one that can prevent it. In particular:

- Before a command that changes state: a build, a migration, a deploy, a release, a force push.
- Before choosing a library, a pattern or an approach, where the project may have tried one and
  rejected it.
- Before editing configuration, CI, or anything under a path you have not touched this session.
- When something looks like a decision that may already have been made.

## What not to do

- Do not paste secrets, credentials or customer data into a search.
<!-- abstention-sensitive -->
- Do not treat memory as authoritative over the code in front of you. A note records what was true
  when it was written; the repository records what is true now. **When they disagree, the code wins
  and the note is worth correcting.**
- Do not search once, find nothing, and conclude the project has no opinion. That is the exact
  failure measured above.
<!-- /abstention-sensitive -->
