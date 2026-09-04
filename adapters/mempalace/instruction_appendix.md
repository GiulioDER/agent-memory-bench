## Reading a `mempalace_search` result

Results are drawers: verbatim slices of an earlier session, not summaries.

- **`wing` / `room`** locate the drawer. `wing` is the project, `room` the topic.
- **`source`** names the session the text came from, which is how you tell a decision recorded
  about this repository from one recorded about another.
- **`cosine_sim`** and **`bm25`** are scored separately and both are reported. A high `bm25` with a
  low `cosine_sim` is a literal keyword hit and is usually the one you want for an error string or
  a filename.
- Drawer text is stored **verbatim**, so a hit may arrive mid-sentence or still carry the JSON
  quoting of the transcript it came from. Read through that rather than discarding the hit.
