from __future__ import annotations

import hashlib
import io
import time
import uuid
from typing import Optional

from utils.logging import get_logger
from .db import LearnDB
from .schemas import Material, MaterialKind

LOGGER = get_logger("preppy.learn.ingest")


def compute_content_hash(raw_bytes: bytes) -> str:
    """Computes SHA-256 hash of document content for deduplication."""
    return hashlib.sha256(raw_bytes).hexdigest()


def ingest_document(
    title: str,
    content: str | bytes,
    kind: MaterialKind = MaterialKind.notes,
    file_type: str = "txt",
    student_id: str = "local",
    source_ref: Optional[str] = None,
    db: Optional[LearnDB] = None,
) -> Material:
    """
    Ingests and normalizes learning materials (PDF, Markdown, TXT) into normalized format.
    Self-contained parser without external legacy dependencies.
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
        okf_text = content
    else:
        content_bytes = content
        if file_type.lower() == "pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                pages_text = [page.extract_text() or "" for page in reader.pages]
                okf_text = "\n\n".join(t for t in pages_text if t.strip())
            except Exception:
                okf_text = content.decode("utf-8", errors="replace")
        else:
            okf_text = content.decode("utf-8", errors="replace")

    content_hash = compute_content_hash(content_bytes)
    clean_title = title.strip() or "Untitled Material"
    material_id = f"mat_{uuid.uuid4().hex[:10]}"

    material = Material(
        id=material_id,
        student_id=student_id,
        title=clean_title,
        kind=kind,
        source_ref=source_ref,
        content_hash=content_hash,
        okf_text=okf_text,
        created_at=int(time.time()),
    )

    if db is not None:
        db.save_material(material)
        LOGGER.info("Ingested and saved material '%s' (%s) kind=%s", clean_title, material_id, kind.value)

    return material


def normalize_text_for_search(text: str) -> str:
    """Collapses whitespace and lowercases text for robust substring matching."""
    return " ".join(text.lower().split())


def verify_span_in_material(material: Material, quote: str) -> bool:
    """
    Deterministically verifies that the quoted source span is a genuine substring of
    the stored material text (§5.1). Rejects hallucinations or fabricated quotes.
    """
    if not quote or not quote.strip():
        return False

    clean_quote = normalize_text_for_search(quote)
    clean_text = normalize_text_for_search(material.okf_text)

    return clean_quote in clean_text
