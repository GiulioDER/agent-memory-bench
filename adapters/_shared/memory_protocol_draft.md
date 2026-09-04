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

You cannot name a symptom you have not hit yet, and you cannot describe a hazard you do not know
exists. What you always have is **the text you are about to write**: the file contents, the edit,
the command. Search with that text itself, not with a description of what you are trying to achieve.

So the search that works is the one issued with your draft in hand, a moment before you save it:

- About to write `version_file.write_text(content, encoding="utf-8")`? Search with that line.
- About to run `alembic upgrade head` against production? Search with that command.
- About to add `requests = "^2.31"` to a manifest? Search with that fragment.

The reason this works is not subtle. A note about a failure contains the literal identifiers the
failure happened in, and so does your draft; a description of your goal contains neither. In the
recorded miss above, "version bump" appears nowhere in the note, but the note's own fix line is
`path.write_text(text, encoding="utf-8", newline="\n")`, which shares four identifiers with the
draft that was about to be saved and none with the goal.

Short is fine and short is normal: one edit hunk or one command is a complete query. Do not
assemble a summary of your plan, and do not paste an entire file.

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
