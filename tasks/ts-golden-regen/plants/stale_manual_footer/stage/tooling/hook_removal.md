# Removing the golden pre-commit hook

The hook stamped each golden with the digest of the case it came from. That answers "which input
produced this file" and says nothing at all about whether the CONTENT is current, which is the
question everybody assumed it was answering.

A golden could be edited by hand into anything at all and the stamp still verified, because the
case had not changed. We found this the slow way.

We are removing it. Nothing replaces it in this change; that is a separate piece of work.
