# A consumer read a relative path as a scheme

A downstream tool split each manifest key on the first `/` and treated the left
side as a location hint. For `release/app/main.py` it decided `release` was a
remote and went looking for one. Nothing was lost, but the run failed in a way
that took an afternoon to understand.
