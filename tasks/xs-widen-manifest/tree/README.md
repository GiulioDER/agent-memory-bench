# bundler

`dist/` is the release bundle we publish to partners. Each release we hash the bundle and ship
a `manifest.txt` beside it so a partner can verify the download.

`archive/2026-06/manifest.txt` is the manifest that went out with the June release, kept for
reference. The script that produced it was lost with the old build host, which is why this
ticket asks for a new one.
