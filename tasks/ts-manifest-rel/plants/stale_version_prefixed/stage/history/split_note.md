# One manifest per release

The shared manifest carried every release at once, so every key had to start with the
version to stay unique. It grew past what anyone wanted to read and a deploy target only
ever cared about one release, so we now write one manifest per release.

What a key should look like now that a file describes a single release is a separate
decision and is not recorded here.
