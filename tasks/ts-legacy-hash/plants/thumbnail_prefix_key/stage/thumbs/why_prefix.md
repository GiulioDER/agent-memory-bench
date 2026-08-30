# Why a prefix and not another digest

Hashing a digest buys nothing: the id is already uniform from its first character. Taking a
prefix is cheaper and keeps the key readable in a directory listing.

This reasoning depends entirely on the ids being digests. An id with human-chosen structure
at the front is a different case, and this note makes no claim about one. Whether a prefix
key is safe there is somebody else's question about somebody else's cache.
