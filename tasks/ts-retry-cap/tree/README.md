# syncer

Pulls partner feeds on a schedule. `client.py` wraps the transport layer; a transport is any
callable taking a url and returning the response text, raising TransportError on failure.
