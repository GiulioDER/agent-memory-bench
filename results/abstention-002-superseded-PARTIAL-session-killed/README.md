# PARTIAL: 86 of 90 sessions, killed by an external process termination

Not a benchmark failure. The pilot exited 1073807364 (0x40010004,
DBG_TERMINATE_PROCESS): the process was terminated by its parent, which lines up with the CLI
session restarting and tearing down the background shell that owned it.

The sessions themselves ran normally. There is no admission.json because the run was killed before
the condition finalised, so these records were never admitted or discarded and must not be
analysed. `superseded` was re-run from scratch, detached from any session, and that run is the one
reported.

Kept as evidence of the failure mode: a long run must not be a child of an interactive session.
