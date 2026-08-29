# INC-4402, the import that buried the queue

A client imported forty thousand records in one batch. Every one of
them carried the highest priority the client's own system used, which
mapped straight through.

For eleven days the walker saw nothing but that import. Ordinary work
raised by hand sat behind it and two escalations were missed.

The fix was to stop trusting the field on the bulk path. A record
raised one at a time is reviewed by a person and was left alone.
