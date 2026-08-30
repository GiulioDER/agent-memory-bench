# Thumbnail cache keys

Asset ids are content digests, so their first characters are already uniformly
distributed. The cache takes the first fifteen characters, with `/` replaced by
`_`, and that has never collided.
