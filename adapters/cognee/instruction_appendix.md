## Reading a `mcp__cognee__recall` result

Results come back as text blocks, one per hit, separated by a blank line and sometimes prefixed
with a `[source]` marker naming the document the text came from.

- **The wording may not be the transcript's.** cognee stores a knowledge graph extracted from the
  documents, and `recall` picks its own strategy unless you name one, so a hit can be a synthesised
  answer rather than a verbatim quote. Read it as a claim about what was recorded, not as the
  record itself.
- **`search_type="CHUNKS"`** returns the stored text of the matching chunks instead, which is what
  you want when the exact wording matters: an error string, a filename, a flag.
- **A `[source]` marker names the session** the material came from. Rendered session names mirror
  their corpus paths, so `sessions__ts-dedup-order__p01` is one session about one topic.
- **`top_k` defaults to 15** and can be raised for a broad question or lowered for a precise one.
