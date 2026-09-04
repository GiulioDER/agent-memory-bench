# Why the vendor manifest is keyed by digest

Vendor drops routinely ship the same blob at several paths. Keying on the digest
makes that visible and lets the importer fetch each distinct blob once; keying on
the path would hide it and we would download the same bytes four times.

This is a property of the VENDOR index, which exists to deduplicate. A manifest
whose job is to describe what a release contains has the opposite requirement:
every path must appear, including two paths holding identical bytes. That is not
this file's problem.
