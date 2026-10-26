from __future__ import annotations

import re
from typing import Callable,Literal
from pydantic import BaseModel
from models.data_models import Module,RetrievedDocument

Label=Literal["grounded", "weak", "unproved"]

class RequirementGrounding(BaseModel):
    step_objective: str
    requirement: str
    coverage: float
    label: Label
    best_distance: float | None = None
    sources: list[str] = []
    missing:list[str]=[]

class ModuleGrounding(BaseModel):
    module_title:str
    items:list[RequirementGrounding]

    @property
    def counts(self) -> dict[str, int]:
        return {name: sum(1 for i in self.items if i.label == name) for name in ("grounded", "weak", "unproved")}

    @property
    def label(self) -> Literal["grounded", "partial", "unproved"]:
        c = self.counts
        if c["grounded"] + c["weak"] == 0:
            return "unproved"
        if c["weak"] == 0 and c["unproved"] == 0:
            return "grounded"
        return "partial"

_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "do", "does", "did", "how", "what",
    "which", "when", "where", "why", "who", "can", "could", "should", "would", "you", "your", "i",
    "it", "its", "to", "of", "in", "on", "for", "with", "and", "or", "if", "that", "this", "these",
    "those", "as", "by", "from", "at", "into", "use", "using", "used", "between", "correct", "way",
    "need", "make", "get", "set", "so", "not", "than", "then", "there", "their", "one",
}

def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word

def _split_identifier(token: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", token)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", spaced)
    return [p.lower() for p in spaced.split("_") if p]

def _analyse(text: str) -> tuple[set[str], set[str]]:
    """
    Abbreviation parts are the pieces of compound identifiers (the `max` in `max_length`).
    A requirement word such as "maximum" counts as found if it starts with one of them.
    """
    words: set[str] = set()
    abbreviations: set[str] = set()
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        pieces = [p for p in _split_identifier(token) if p not in _STOP and len(p) > 2]
        words.update(_stem(p) for p in pieces)
        if len(_split_identifier(token)) > 1:
            abbreviations.update(pieces)
    return words, abbreviations




def content_words(text: str) -> set[str]:
    return _analyse(text)[0]

def _surface(text: str) -> dict[str, str]:
    """stem -> the word as written, so diagnostics show 'kubernetes' and not 'kubernet'."""
    out: dict[str, str] = {}
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        for piece in _split_identifier(token):
            if piece not in _STOP and len(piece) > 2:
                out.setdefault(_stem(piece), piece)
    return out

def uncovered_words(requirement: str, retrieved_texts: list[str]) -> list[str]:
    """The requirement's content words (as written) that the retrieved text does not contain."""
    surface = _surface(requirement)
    found, abbreviations = _analyse(" ".join(retrieved_texts))
    return sorted(
        word for stem, word in surface.items()
        if stem not in found and not any(stem.startswith(a) for a in abbreviations)
    )

def lexical_coverage(requirement:str,retrieved_texts:list[str]) ->float:
    "Share of the requirement's content words that appear in the retrieved text."
    wanted=content_words(requirement)
    if not wanted:
        return 1.0
    found=content_words(" ".join(retrieved_texts))
    return 1 - len(uncovered_words(requirement, retrieved_texts)) / len(wanted)

def grounding_label(coverage: float,*,min_for_grounded: float = 0.60,min_for_weak: float = 0.40) -> Label:
    if coverage >= min_for_grounded:
        return "grounded"
    if coverage >= min_for_weak:
        return "weak"
    return "unproved"

def _source(doc:RetrievedDocument)->str:
    return f"{doc.metadata.get('url',doc.metadata.get('source_file'))}{doc.metadata.get('anchor')}"

def ground_module(
        module:Module,
        retrieve:Callable[[str],list[RetrievedDocument]],
        *,
        max_sources:int=3,
        min_for_grounded: float = 0.60,
        min_for_weak: float = 0.40,
    ) -> ModuleGrounding:

    items: list[RequirementGrounding] = []
    for step in module.steps:
        for requirement in step.requirements:
            docs = retrieve(requirement)
            coverage = lexical_coverage(requirement, [d.content for d in docs])
            items.append(
                RequirementGrounding(
                    step_objective=step.objective,
                    requirement=requirement,
                    coverage=round(coverage, 3),
                    missing=uncovered_words(requirement,[d.content for d in docs]),
                    label=grounding_label(coverage,min_for_grounded=min_for_grounded,min_for_weak=min_for_weak),
                    best_distance=min((d.distance for d in docs), default=None),
                    sources=list(dict.fromkeys(_source(d) for d in docs))[:max_sources],
                )
            )
    return ModuleGrounding(module_title=module.title, items=items)