from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path

# Headings/Links CleanUp
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_PERMALINK = re.compile(r"\[¶\]\((?P<url>[^)\s]+)[^)]*\)")

@dataclass(frozen=True)
class Section:
    id:int
    page_title:str
    heading:str
    subheadings:tuple[str,...]
    body:str
    source:str|None


def _clean(text: str) -> str:
    # Remove markdown formatting that is unnecessary for the outline.
    text = _PERMALINK.sub("", text).replace("`", "").replace("**", "")
    return re.sub(r"\s+", " ", text).strip()

def _parse_page(text: str, fallback_title: str) -> tuple[str, list[dict]]:
    "Split one markdown page into H2 sections."
    page_title: str | None = None
    page_source: str | None = None
    sections: list[dict] = []
    current: dict | None = None
    in_fence = False

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if current is not None:
                current["body"].append(line)
            continue

        match = None if in_fence else _HEADING.match(line)
        if match:
            level, raw = len(match.group(1)), match.group(2)
            link = _PERMALINK.search(raw)
            title = _clean(raw)
            if level == 1 and page_title is None:
                page_title = title
                page_source = link.group("url") if link else None
                continue
            if level == 2:
                # Completes the previous H2 heading before next one
                if current is not None:
                    sections.append(current)
                current = {
                    "heading": title,
                    "subs": [],
                    "body": [line],
                    "source": link.group("url") if link else None,
                }
                continue
            if level == 3 and current is not None:
                current["subs"].append(title)

        if current is not None:
            current["body"].append(line)

    if current is not None:
        sections.append(current)

    page_title = page_title or fallback_title
    if not sections:
        # store entire page as section if there are no h2
        sections = [{"heading": page_title, "subs": [], "body": text.splitlines(), "source": page_source}]
    return page_title, sections

class DocOutline:
    def __init__(self, sections: list[Section]):
        self.sections = list(sections)
        # Stored sections as dict for faster look up
        self._by_id = {s.id: s for s in self.sections}

    def __len__(self) -> int:
        return len(self.sections)

    @property
    def valid_ids(self) -> set[int]:
        return set(self._by_id)

    @classmethod
    def from_raw_docs(cls, raw_docs_dir: str | Path, order:list[str] | None= None) -> "DocOutline":

        raw_dir = Path(raw_docs_dir)
        manifest_path = raw_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

        ranks={url.rstrip("/"): i for i,url in enumerate(order or [])}

        def rank(md_file: Path) -> int:
            entry = manifest.get(md_file.name, {})
            if ranks:
                return ranks.get(entry.get("url", "").rstrip("/"), len(ranks))
            return entry.get("position",10**9)

        md_files=sorted(raw_dir.glob("*.md"))
        md_files.sort(key=rank)

        sections: list[Section] = []
        next_id = 1
        for md_file in md_files:
            fallback = manifest.get(md_file.name, {}).get("title") or md_file.stem
            page_title, raw_sections = _parse_page(md_file.read_text(encoding="utf-8"), fallback)
            page_title = manifest.get(md_file.name, {}).get("title") or page_title
            for raw in raw_sections:
                body = _PERMALINK.sub("", "\n".join(raw["body"])).strip()
                sections.append(
                    Section(
                        id=next_id,
                        page_title=page_title,
                        heading=raw["heading"],
                        subheadings=tuple(raw["subs"]),
                        body=body,
                        source=raw["source"],
                    )
                )
                next_id += 1
        return cls(sections)

    def render(self) -> str:
        "Renders the Numbered Outlines"
        lines: list[str] = []
        last_page = None
        for s in self.sections:
            if s.page_title != last_page:
                lines.append(f"Page: {s.page_title}")
                last_page = s.page_title
            covers = f" (covers: {'; '.join(s.subheadings)})" if s.subheadings else ""
            lines.append(f"  [{s.id}] {s.heading}{covers}")
        return "\n".join(lines)

    def text_for(self, ids: list[int], max_chars: int = 6000) -> str:
        """Documentation text for the given sections, capped to a budget."""
        wanted = [i for i in dict.fromkeys(ids) if i in self._by_id]
        if not wanted:
            return ""
        per_section = max_chars // len(wanted)
        parts = []
        for i in wanted:
            body = self._by_id[i].body
            if len(body) > per_section:
                body = body[:per_section].rstrip() + "\n...[truncated]"
            parts.append(body)
        return "\n\n".join(parts)

    def sources_for(self, ids: list[int]) -> list[str]:
        return [
            self._by_id[i].source or self._by_id[i].heading
            for i in dict.fromkeys(ids)
            if i in self._by_id
        ]