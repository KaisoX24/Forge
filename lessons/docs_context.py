from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Callable

from exercises.grounding import grounding_label, lexical_coverage, uncovered_words
from models.data_models import ObjectivePlan, RetrievedDocument
from models.lesson_generation_models import DocRef, Label

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 3.5
_PLACEHOLDER_NUMBER = 99


# token budget
def estimate_tokens(text: str, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    return math.ceil(len(text) / chars_per_token) if text else 0


def docs_budget(*, num_ctx: int = 8192, num_predict: int = 2048, fixed_prompt_tokens: int = 1000,
                margin: float = 0.10) -> int:
    """Tokens left for documentation: the window, minus the room reserved for the answer, minus the
    fixed part of the prompt (rules, step, earlier-step titles), minus a safety margin for the estimate."""
    budget = num_ctx - num_predict - fixed_prompt_tokens - int(num_ctx * margin)
    if budget <= 0:
        raise ValueError(f"No room left for documentation (budget {budget}); raise num_ctx or shrink the prompt.")
    return budget


# reading chunk metadata
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HEADERS = ("Header 4", "Header 3", "Header 2", "Header 1")


def clean_heading(text: str) -> str:
    "'Path Parameters[¶](https://… \"Permanent link\")' -> 'Path Parameters'"
    text = _LINK.sub(lambda m: m.group(1), text).replace("¶", "")
    return re.sub(r"\s+", " ", text).strip()


def chunk_title(doc: RetrievedDocument) -> str | None:
    "The most specific heading the chunk sits under (the one its anchor points at)."
    for level in _HEADERS:
        title = clean_heading(doc.metadata.get(level, ""))
        if title:
            return title
    return None


def _page(doc: RetrievedDocument) -> str:
    return doc.metadata.get("url") or doc.metadata.get("source_file") or "unknown"


def source_url(doc: RetrievedDocument) -> str:
    "Page URL plus the section anchor, so a link lands on the right section."
    return f"{_page(doc)}{doc.metadata.get('anchor') or ''}"


def _chunk_key(doc: RetrievedDocument) -> str:
    return doc.metadata.get("chunk_id") or hashlib.sha1(doc.content.encode("utf-8")).hexdigest()


#  rendering and packing
def render_chunk(doc: RetrievedDocument, number: int) -> str:
    return f"[Source {number}] {chunk_title(doc) or _page(doc)} ({source_url(doc)})\n{doc.content.strip()}\n\n"


def render_docs(chunks: list[RetrievedDocument]) -> str:
    return "".join(render_chunk(c, n) for n, c in enumerate(chunks, 1)).rstrip()


@dataclass(frozen=True)
class PackedDocs:
    chunks: list[RetrievedDocument]      
    est_tokens: int
    dropped: int                         


def pack_docs(results: list[list[RetrievedDocument]], budget_tokens: int, *,
              chars_per_token: float = CHARS_PER_TOKEN) -> PackedDocs:
    ranked: list[RetrievedDocument] = []
    seen: set[str] = set()
    for rank in range(max((len(r) for r in results), default=0)):
        for docs in results:
            if rank < len(docs) and _chunk_key(docs[rank]) not in seen:
                seen.add(_chunk_key(docs[rank]))
                ranked.append(docs[rank])

    chosen: list[RetrievedDocument] = []
    used = dropped = 0
    for doc in ranked:
        cost = estimate_tokens(render_chunk(doc, _PLACEHOLDER_NUMBER), chars_per_token)
        if used + cost <= budget_tokens:
            chosen.append(doc)
            used += cost
        else:
            dropped += 1

    first_seen: dict[str, int] = {}
    for doc in chosen:
        first_seen.setdefault(_page(doc), len(first_seen))
    chosen.sort(key=lambda d: first_seen[_page(d)])
    return PackedDocs(chunks=chosen, est_tokens=used, dropped=dropped)


# grounding, one label per step
@dataclass(frozen=True)
class StepGrounding:
    label: Label
    coverage: float                                   
    per_requirement: list[tuple[str, float]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list) 


def ground_step(requirements: list[str], chunks: list[RetrievedDocument], *,
                min_for_grounded: float = 0.60, min_for_weak: float = 0.40) -> StepGrounding:
    """Measured on ALL the chunks the model sees: a requirement counts as covered if anything it was
    shown covers it. A step is only as grounded as its weakest requirement."""
    texts = [c.content for c in chunks]
    per = [(req, round(lexical_coverage(req, texts), 3)) for req in requirements]
    coverage = min((c for _, c in per), default=0.0)
    missing = sorted({w for req in requirements for w in uncovered_words(req, texts)})
    return StepGrounding(
        label=grounding_label(coverage, min_for_grounded=min_for_grounded, min_for_weak=min_for_weak),
        coverage=coverage, per_requirement=per, missing=missing)


def build_doc_refs(chunks: list[RetrievedDocument], grounding: StepGrounding) -> list[DocRef]:
    "One DocRef per distinct source section; each carries the step's label and coverage."
    refs: list[DocRef] = []
    seen: set[str] = set()
    for chunk in chunks:
        url = source_url(chunk)
        if url in seen:
            continue
        seen.add(url)
        refs.append(DocRef(label=chunk_title(chunk) or url, url=url,
                           grounding=grounding.label, coverage=grounding.coverage))
    return refs


# the one call the generator makes
@dataclass(frozen=True)
class StepDocs:
    packed: PackedDocs
    text: str
    refs: list[DocRef]
    grounding: StepGrounding


def prepare_step_docs(step: ObjectivePlan, retrieve: Callable[[str], list[RetrievedDocument]], *,
                      budget_tokens: int, chars_per_token: float = CHARS_PER_TOKEN,
                      min_for_grounded: float = 0.60, min_for_weak: float = 0.40) -> StepDocs:
    "Queries are the step's requirements (the same ones the planner's grounding used)."
    requirements = list(step.requirements)
    packed = pack_docs([retrieve(q) for q in requirements], budget_tokens, chars_per_token=chars_per_token)
    grounding = ground_step(requirements, packed.chunks, min_for_grounded=min_for_grounded, min_for_weak=min_for_weak)
    logger.info("step docs: %d chunks (~%d of %d tokens), %d dropped, grounding=%s (%.2f)",
                len(packed.chunks), packed.est_tokens, budget_tokens, packed.dropped, grounding.label, grounding.coverage)
    return StepDocs(packed=packed, text=render_docs(packed.chunks),
                    refs=build_doc_refs(packed.chunks, grounding), grounding=grounding)