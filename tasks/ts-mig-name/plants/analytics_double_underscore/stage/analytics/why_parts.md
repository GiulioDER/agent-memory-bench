# Why analytics filenames are parsed, not read

The analytics migrations are generated from a schema description and replayed by
a tool that needs to know which table each one touches without opening it. The
double underscore is a delimiter chosen because no identifier contains one.

Nothing constrains their length: the analytics database is ours and imposes no
identifier limit. A database that DOES impose one would need a different rule,
and that is not this directory's problem.
