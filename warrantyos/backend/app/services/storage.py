"""
Secure file storage abstraction — Part 1.2

Local filesystem for hackathon, cloud-ready via `StorageBackend` interface.
Never trusts user filenames, prevents path traversal, validates size/MIME.
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import BinaryIO, Tuple

from fastapi import HTTPException, status, UploadFile

from app.core.config import get_settings

settings = get_settings()

# Configurable allowed types (MIME)
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
    "video/mp4",
    "video/quicktime",
    "text/plain",
}

# Extension fallback map for MIME not in ALLOWED but extension allowed
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".mp4", ".mov", ".txt"}

MAX_FILE_SIZE = settings.MAX_UPLOAD_MB * 1024 * 1024  # bytes
UPLOAD_DIR = Path(settings.UPLOAD_DIR)


def ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(original: str) -> str:
    """Strip path, keep basename only, remove traversal attempts."""
    # Use Path.name to get basename
    name = Path(original).name
    # Remove null bytes and control chars
    name = name.replace("\x00", "")
    # If empty after sanitization, generate
    if not name or name.strip() in (".", ".."):
        name = "file"
    return name


def _get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_file(file: UploadFile):
    # MIME check
    mime = file.content_type or "application/octet-stream"
    ext = _get_extension(file.filename or "")
    if mime not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {mime or ext}. Allowed: images, PDF, MP4, txt",
        )
    # Size will be checked during read; fail early if content-length header present?
    # We enforce during streaming below.


def generate_stored_filename(original: str) -> str:
    ext = _get_extension(original)
    # Preserve extension for MIME detection, but generate random name
    return f"{uuid.uuid4().hex}{ext}"


def save_upload(file: UploadFile, claim_id: int) -> Tuple[str, str, int, str]:
    """
    Save file securely to UPLOAD_DIR/<claim_id>/<uuid>.<ext>
    Returns (file_path_str, stored_filename, file_size, mime_type)
    Validates size and MIME.
    """
    validate_file(file)
    ensure_upload_dir()
    claim_dir = UPLOAD_DIR / str(claim_id)
    claim_dir.mkdir(parents=True, exist_ok=True)

    original = _safe_filename(file.filename or "file")
    stored = generate_stored_filename(original)
    dest = claim_dir / stored

    # Prevent path traversal — ensure dest is inside claim_dir
    try:
        dest.resolve().relative_to(claim_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path.")

    mime = file.content_type or "application/octet-stream"
    size = 0
    # Stream write with size enforcement
    # UploadFile.file is SpooledTemporaryFile
    file.file.seek(0)
    with open(dest, "wb") as out:
        while True:
            chunk = file.file.read(8192)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                out.close()
                # cleanup partial file
                try:
                    os.remove(dest)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max {settings.MAX_UPLOAD_MB} MB",
                )
            out.write(chunk)

    # Reset for potential re-read
    file.file.seek(0)
    # Return relative path for DB (not absolute) — e.g., "5/abc123.pdf"
    rel_path = f"{claim_id}/{stored}"
    return rel_path, stored, size, mime


def delete_file(rel_path: str):
    """Delete file given relative path like 'claim_id/stored'."""
    # Prevent traversal
    p = UPLOAD_DIR / rel_path
    try:
        # ensure p is inside UPLOAD_DIR
        p.resolve().relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        return
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass
