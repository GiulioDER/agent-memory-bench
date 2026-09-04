# A join that misses on case

One partner ships ids uppercase and another mixes case. The downstream join is
case sensitive, so rows that should match do not, and nothing errors: the
unmatched rows are simply absent from the report.
