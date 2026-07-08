import email
import email.policy
import io
import os

from fastapi import HTTPException, UploadFile

from ..hashing import image_hash, text_hash, video_hash

TEXT_EXTENSIONS = {".txt", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


async def read_input(
    file: UploadFile | None,
    text: str | None,
    media_type: str | None,
) -> tuple[str, str | bytes, str]:
    """Normalizes the two input modes (raw text or file upload) into
    (media_type, content, filename_suffix). Text-bearing files (.txt, .eml,
    .pdf) are extracted to plain text here."""
    if text is not None and text.strip():
        return "text", text, ""
    if file is None:
        raise HTTPException(status_code=400, detail="provide a file or a text field")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    suffix = os.path.splitext(file.filename or "")[1].lower()

    if suffix == ".eml":
        return "text", _extract_eml(data), suffix
    if suffix == ".pdf":
        return "text", _extract_pdf(data), suffix

    if media_type in {"text", "image", "video"}:
        resolved = media_type
    elif suffix in TEXT_EXTENSIONS:
        resolved = "text"
    elif suffix in IMAGE_EXTENSIONS:
        resolved = "image"
    elif suffix in VIDEO_EXTENSIONS:
        resolved = "video"
    else:
        content_type = file.content_type or ""
        if content_type.startswith("text/"):
            resolved = "text"
        elif content_type.startswith("image/"):
            resolved = "image"
        elif content_type.startswith("video/"):
            resolved = "video"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"could not determine media type for '{file.filename}'; "
                "pass media_type=text|image|video",
            )

    if resolved == "text":
        try:
            return "text", data.decode("utf-8", errors="replace"), suffix
        except Exception:
            raise HTTPException(status_code=400, detail="could not decode text file")
    return resolved, data, suffix


def compute_hashes(
    media_type: str, content: str | bytes, suffix: str = ".mp4"
) -> tuple[str, list[str]]:
    try:
        if media_type == "text":
            return text_hash.compute(content)
        if media_type == "image":
            return image_hash.compute(content)
        if media_type == "video":
            return video_hash.compute(content, suffix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=400, detail=f"could not process {media_type} input")
    raise HTTPException(status_code=400, detail=f"unsupported media type '{media_type}'")


def _extract_eml(data: bytes) -> str:
    message = email.message_from_bytes(data, policy=email.policy.default)
    body = message.get_body(preferencelist=("plain", "html"))
    content = body.get_content() if body else ""
    subject = message.get("subject", "")
    text = f"{subject}\n{content}".strip()
    if not text:
        raise HTTPException(status_code=400, detail="no text found in .eml file")
    return text


def _extract_pdf(data: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    if not text:
        raise HTTPException(status_code=400, detail="no extractable text in PDF")
    return text
