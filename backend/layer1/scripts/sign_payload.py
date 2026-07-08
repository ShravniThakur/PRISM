#!/usr/bin/env python3
"""Sign a /sign/prepare payload locally with an entity's private key.

This is what the Entity Portal does client-side: the private key never
touches the PRISM server.

Usage:
    python scripts/sign_payload.py --key sebi_private.pem --payload-b64 <b64>
"""
import argparse
import base64
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.crypto import signing  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, help="path to the private key PEM")
    parser.add_argument(
        "--payload-b64", required=True, help="payload_b64 from POST /sign/prepare"
    )
    args = parser.parse_args()

    private_pem = pathlib.Path(args.key).read_text()
    print(signing.sign(private_pem, base64.b64decode(args.payload_b64)))


if __name__ == "__main__":
    main()
