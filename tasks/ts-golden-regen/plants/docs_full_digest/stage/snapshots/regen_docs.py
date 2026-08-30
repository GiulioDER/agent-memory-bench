"""Regenerate docs/api-snapshot.md from the public surface."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    body = render_surface()
    # Full digest, not truncated. See snapshots/collision.md.
    digest = hashlib.sha256(body.encode()).hexdigest()
    out = ROOT / 'docs' / 'api-snapshot.md'
    out.write_text(body + '\n# sha256:' + digest + '\n', encoding='utf-8')
