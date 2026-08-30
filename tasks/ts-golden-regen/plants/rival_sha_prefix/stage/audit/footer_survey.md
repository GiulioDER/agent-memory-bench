# Checksum footers across the repository

| artefact | footer prefix |
|---|---|
| `dist/manifest.json` | `# sha:` |
| `vendor/licences.txt` | `# sha:` |
| `docs/api-snapshot.md` | `# sha:` |
| `tests/golden/*.out` | `# golden:` |

One artefact out of four spells it differently. Nothing depends on the spelling; the verifier
reads whichever it finds.
