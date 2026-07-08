from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import VerifyOut
from ..services import media, verify_service

router = APIRouter(tags=["verification"])


@router.post("/verify", response_model=VerifyOut)
async def verify(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    media_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Investor-facing check: recomputes the fuzzy hash of the upload, finds
    the closest signed original, and verifies its signature. The
    `is_authenticated_sender` field feeds the Random Forest scoring engine."""
    resolved_type, content, suffix = await media.read_input(file, text, media_type)
    algorithm, hashes = media.compute_hashes(resolved_type, content, suffix)
    return verify_service.verify(db, resolved_type, algorithm, hashes)
