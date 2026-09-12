"""Issue, finalize, or verify trusted execution receipts.

Examples:

    python -m scripts.adjudicate_run keygen private.key --public-out public.key
    python -m scripts.adjudicate_run issue results/run-condition --run-id run-condition \
        --runner-image-digest sha256:... --participant-agent-digest sha256:... \
        --oracle-version sha256:...
    python -m scripts.adjudicate_run finalize results/run-condition --key-file private.key
    python -m scripts.adjudicate_run verify results/run-condition --public-key-file public.key
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from harness.adjudication import (
    AdjudicationError,
    adjudicate_run,
    generate_private_key,
    issue_challenge,
    load_private_signer,
    verify_receipt,
)


def _public_key(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) == 32:
        return raw
    try:
        return base64.urlsafe_b64decode(raw.decode("ascii").strip() + "=" * (-len(raw.strip()) % 4))
    except (UnicodeDecodeError, ValueError) as error:
        raise AdjudicationError(f"public key is not raw or base64url: {path}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="create a raw Ed25519 private key")
    keygen.add_argument("path", type=Path)
    keygen.add_argument("--public-out", type=Path, required=True)

    issue = sub.add_parser("issue", help="issue a one time challenge before execution")
    issue.add_argument("run_dir", type=Path)
    issue.add_argument("--run-id", required=True)
    issue.add_argument("--runner-image-digest", required=True)
    issue.add_argument("--participant-agent-digest", required=True)
    issue.add_argument("--oracle-version", required=True)

    finalize = sub.add_parser("finalize", help="sign a completed execution")
    finalize.add_argument("run_dir", type=Path)
    finalize.add_argument("--key-file", type=Path, required=True)
    finalize.add_argument("--key-id", default="adjudicator")
    finalize.add_argument("--ledger", type=Path)

    verify = sub.add_parser("verify", help="verify a receipt and its bound evidence")
    verify.add_argument("run_dir", type=Path)
    verify.add_argument("--public-key-file", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            public_key = generate_private_key(args.path)
            args.public_out.write_text(public_key + "\n", encoding="ascii", newline="\n")
            print(json.dumps({"private_key": str(args.path), "public_key": public_key}, indent=2))
        elif args.command == "issue":
            challenge = issue_challenge(
                args.run_dir,
                run_id=args.run_id,
                runner_image_digest=args.runner_image_digest,
                participant_agent_digest=args.participant_agent_digest,
                oracle_version=args.oracle_version,
            )
            print(json.dumps(challenge.to_dict(), indent=2))
        elif args.command == "finalize":
            receipt = adjudicate_run(
                args.run_dir,
                signer=load_private_signer(args.key_file, key_id=args.key_id),
                ledger_path=args.ledger,
            )
            print(json.dumps(receipt, indent=2))
        else:
            receipt = verify_receipt(args.run_dir, public_key=_public_key(args.public_key_file))
            print(json.dumps({"receipt_id": receipt["receipt_id"], "verified": True}, indent=2))
    except (AdjudicationError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f"adjudication failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
