from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from utils.logging import get_logger
from .config import (
    DEFAULT_MAX_CONCEPTS_PER_MATERIAL,
    DEFAULT_MAX_CONCEPT_DEPTH,
)
from .db import LearnDB
from .ingest import verify_span_in_material
from .llm import LLMClient, LearnAIError, get_llm_client
from .schemas import Concept, Mastery, MasteryBand, Material, MaterialKind, SourceSpan

LOGGER = get_logger("blinky.learn.concepts")


class ExtractedConceptItem(BaseModel):
    name: str
    description: str = ""
    parent_name: Optional[str] = None
    prerequisite_names: List[str] = Field(default_factory=list)
    source_quote: Optional[str] = None


class ExtractedConceptsResponse(BaseModel):
    concepts: List[ExtractedConceptItem]


def extract_concepts_offline(material: Material) -> List[Concept]:
    """
    Deterministic rule-based concept extractor that runs with ZERO AI dependencies.
    Extracts Markdown headers (#, ##, ###) and structured bullet lines from material.
    """
    lines = material.okf_text.splitlines()
    raw_concepts: List[Dict[str, Any]] = []
    current_parent_id: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("### SOURCE:") or stripped.startswith("Type:"):
            continue

        # Match markdown headers
        header_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if header_match:
            level = len(header_match.group(1))
            name = header_match.group(2).strip()
            cid = f"c_{uuid.uuid4().hex[:8]}"
            parent = current_parent_id if level > 1 else None
            if level == 1:
                current_parent_id = cid

            raw_concepts.append({
                "id": cid,
                "name": name,
                "description": f"Extracted from section {name}",
                "parent_id": parent,
                "source_quote": name,
            })
            continue

        # Match bullet points or numbered lists under headers
        bullet_match = re.match(r"^(?:[-*•]|\d+[\.)])\s+(.*)$", stripped)
        if bullet_match and len(raw_concepts) < DEFAULT_MAX_CONCEPTS_PER_MATERIAL:
            bullet_text = bullet_match.group(1).strip()
            # If line is concise, treat as concept
            if 3 < len(bullet_text) <= 80:
                cid = f"c_{uuid.uuid4().hex[:8]}"
                raw_concepts.append({
                    "id": cid,
                    "name": bullet_text,
                    "description": f"Topic under {current_parent_id or material.title}",
                    "parent_id": current_parent_id,
                    "source_quote": bullet_text,
                })

    # If no headers or bullets matched, create one root concept from title
    if not raw_concepts:
        root_id = f"c_{uuid.uuid4().hex[:8]}"
        raw_concepts.append({
            "id": root_id,
            "name": material.title,
            "description": f"Core topics for {material.title}",
            "parent_id": None,
            "source_quote": material.title,
        })

    return _post_process_concepts(raw_concepts, material)


def _post_process_concepts(raw_items: List[Dict[str, Any]], material: Material) -> List[Concept]:
    """
    Applies deterministic constraints:
    1. Deduplicates concept names.
    2. Enforces max depth <= 3.
    3. Caps concept count <= DEFAULT_MAX_CONCEPTS_PER_MATERIAL (25).
    4. Deterministically validates source quote substring for notes/textbooks.
    """
    seen_names = set()
    deduped: List[Dict[str, Any]] = []

    for item in raw_items:
        clean_name = item.get("name", "").strip()
        if not clean_name:
            continue
        lower_name = clean_name.lower()
        if lower_name in seen_names:
            continue
        seen_names.add(lower_name)
        deduped.append(item)
        if len(deduped) >= DEFAULT_MAX_CONCEPTS_PER_MATERIAL:
            break

    # Build id lookup and depth calculation
    id_to_parent: Dict[str, Optional[str]] = {it["id"]: it.get("parent_id") for it in deduped}

    def get_depth(node_id: str) -> int:
        depth = 1
        curr = id_to_parent.get(node_id)
        visited = {node_id}
        while curr and curr in id_to_parent and curr not in visited:
            depth += 1
            visited.add(curr)
            curr = id_to_parent[curr]
        return depth

    result: List[Concept] = []
    is_syllabus = material.kind == MaterialKind.syllabus

    for idx, it in enumerate(deduped):
        cid = it["id"]
        parent_id = it.get("parent_id")

        # Cap depth at 3 (§5.1)
        if parent_id and get_depth(cid) > DEFAULT_MAX_CONCEPT_DEPTH:
            parent_id = None  # Flatten deep nesting to root

        spans: List[SourceSpan] = []
        quote = it.get("source_quote") or ""

        if not is_syllabus and quote:
            # Deterministic verification of substring in material
            if verify_span_in_material(material, quote):
                spans.append(
                    SourceSpan(
                        material_id=material.id,
                        source_name=material.title,
                        quote=quote,
                    )
                )

        desc = it.get("description", "")
        if is_syllabus:
            desc = f"[Syllabus Scope] {desc}".strip()

        concept = Concept(
            id=cid,
            material_id=material.id,
            parent_id=parent_id,
            name=it["name"].strip(),
            description=desc,
            order_idx=idx,
            prerequisites=it.get("prerequisites", []),
            source_spans=spans,
        )
        result.append(concept)

    return result


def extract_concepts_from_material(
    material: Material,
    llm_client: Optional[LLMClient] = None,
    db: Optional[LearnDB] = None,
) -> List[Concept]:
    """
    Extracts a structured concept tree from learning material.
    Uses LLM when available; falls back cleanly to deterministic offline extractor if offline.
    """
    client = llm_client or get_llm_client()
    concepts: List[Concept] = []

    # Limit prompt payload to prevent TPM exhaustion on free tiers
    prompt_context = material.okf_text[:6000]

    try:
        response: ExtractedConceptsResponse = client.generate_structured(
            prompt_name="concept_extraction",
            template_args={
                "material_title": material.title,
                "material_kind": material.kind.value,
                "material_text": prompt_context,
            },
            schema=ExtractedConceptsResponse,
            max_retries=2,
            max_tokens=1800,
        )

        # Build parent mapping from proposed names
        name_to_id: Dict[str, str] = {}
        raw_items: List[Dict[str, Any]] = []

        for item in response.concepts:
            cid = f"c_{uuid.uuid4().hex[:8]}"
            name_to_id[item.name.strip().lower()] = cid
            raw_items.append({
                "id": cid,
                "name": item.name.strip(),
                "description": item.description.strip(),
                "parent_name": item.parent_name,
                "prerequisite_names": item.prerequisite_names,
                "source_quote": item.source_quote,
            })

        # Resolve parent_id and prerequisite ids
        for raw in raw_items:
            p_name = (raw.get("parent_name") or "").strip().lower()
            raw["parent_id"] = name_to_id.get(p_name)
            raw["prerequisites"] = [
                name_to_id[p.strip().lower()]
                for p in raw.get("prerequisite_names", [])
                if p.strip().lower() in name_to_id
            ]

        concepts = _post_process_concepts(raw_items, material)
        LOGGER.info("Successfully extracted %s concepts via AI for '%s'", len(concepts), material.title)

    except (LearnAIError, Exception) as exc:
        LOGGER.warning("AI concept extraction failed or unavailable (%s). Using deterministic offline fallback.", exc)
        concepts = extract_concepts_offline(material)

    # Persist and initialize default mastery
    if db is not None and concepts:
        db.save_concepts(concepts)
        for c in concepts:
            existing_m = db.get_mastery(c.id, student_id=material.student_id)
            if existing_m is None:
                default_mastery = Mastery(
                    student_id=material.student_id,
                    concept_id=c.id,
                    mastery=0.50,
                    attempts=0,
                    correct=0,
                    consecutive_correct=0,
                    last_outcomes=[],
                    has_transfer_success=False,
                    consistency=1.0,
                    band=MasteryBand.insufficient_evidence,
                )
                db.save_mastery(default_mastery)

    return concepts
