from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import PrepareOut, SignedAssetOut, SignSubmit
from ..services import media, sign_service

router = APIRouter(prefix="/sign", tags=["signing"])


@router.post("/prepare", response_model=PrepareOut)
async def prepare(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    media_type: str | None = Form(None),
):
    """Computes the fuzzy hash of an asset and returns the canonical payload
    the entity must sign locally with its private key."""
    resolved_type, content, suffix = await media.read_input(file, text, media_type)
    algorithm, hashes = media.compute_hashes(resolved_type, content, suffix)
    return sign_service.prepare(resolved_type, algorithm, hashes)


@router.post("/submit", response_model=SignedAssetOut, status_code=201)
def submit(body: SignSubmit, db: Session = Depends(get_db)):
    """Stores a signed asset record after verifying the signature against the
    entity's active public key."""
    return sign_service.submit(
        db,
        body.entity_id,
        body.payload_b64,
        body.signature_b64,
        body.title,
        body.reference_url,
    )
