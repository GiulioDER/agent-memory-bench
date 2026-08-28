# The ingest's field splitter

It splits on the delimiter and does not implement quoting. This was a
deliberate choice in 2021: the parser is embedded in a device with no
room for a full reader, and it has been correct for every feed whose
values cannot contain the delimiter.
