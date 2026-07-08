#!/usr/bin/env python3
"""Seed the registry with demo entities (SEBI, NSE) and one signed advisory.

Private keys are written to scripts/demo_keys/ so you can sign more assets
with scripts/sign_payload.py during a demo.

Usage:
    python scripts/seed_demo.py
"""
import base64
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.crypto import signing  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.hashing import text_hash  # noqa: E402
from app.models import Entity  # noqa: E402
from app.services import registry, sign_service  # noqa: E402

KEYS_DIR = pathlib.Path(__file__).parent / "demo_keys"

DEMO_ADVISORY = (
    "SEBI Investor Advisory: SEBI has observed fraudulent trading platforms "
    "impersonating registered brokers and promising guaranteed returns. "
    "Investors are advised to transact only through SEBI-registered "
    "intermediaries and to verify registration numbers on the official SEBI "
    "website www.sebi.gov.in before investing. SEBI never solicits "
    "investments or asks for payments to personal accounts."
)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    KEYS_DIR.mkdir(exist_ok=True)
    db = SessionLocal()
    try:
        private_keys: dict[str, str] = {}
        for name, entity_type in [("SEBI", "regulator"), ("NSE", "exchange")]:
            existing = db.query(Entity).filter(Entity.name == name).first()
            if existing:
                print(f"entity {name} already registered ({existing.id}); skipping")
                continue
            entity, private_pem = registry.create_entity(db, name, entity_type)
            key_path = KEYS_DIR / f"{name.lower()}_private.pem"
            key_path.write_text(private_pem)
            private_keys[name] = private_pem
            print(f"registered {name} ({entity.id}); private key -> {key_path}")

        if "SEBI" in private_keys:
            sebi = db.query(Entity).filter(Entity.name == "SEBI").first()
            algorithm, hashes = text_hash.compute(DEMO_ADVISORY)
            prepared = sign_service.prepare("text", algorithm, hashes)
            signature = signing.sign(
                private_keys["SEBI"], base64.b64decode(prepared["payload_b64"])
            )
            asset = sign_service.submit(
                db,
                sebi.id,
                prepared["payload_b64"],
                signature,
                title="SEBI Investor Advisory (demo)",
            )
            print(f"signed demo advisory as SEBI ({asset.id})")
            print("\ntry it:")
            print(
                "  curl -s -X POST http://127.0.0.1:8000/verify "
                f"-F 'text={DEMO_ADVISORY[:60]}...'"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
