# Too many small files

The cache directory reached forty thousand files on one deploy target and
directory listing became the slowest thing in the read path. Any scheme with a
bounded file count fixes it.
