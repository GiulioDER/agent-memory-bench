# Proposal: spell relative paths explicitly

Prefix every generated relative path with `./`. It is unambiguous to every
consumer, it is what shells and POSIX tools already accept, and it costs two
characters per key.
