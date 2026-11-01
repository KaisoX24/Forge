import json
from pathlib import Path

from course_sources import FASTAPI_URLS
from planner.doc_outline import DocOutline

RAW = Path("raw_docs")


def _page_titles(outline: DocOutline) -> list[str]:
    seen: list[str] = []
    for s in outline.sections:
        if s.page_title not in seen:
            seen.append(s.page_title)
    return seen


def test_outline_follows_course_order():
    manifest = json.loads((RAW / "manifest.json").read_text())
    title_by_url = {e["url"].rstrip("/"): e["title"] for e in manifest.values()}
    expected = [title_by_url[u.rstrip("/")] for u in FASTAPI_URLS if u.rstrip("/") in title_by_url]
    assert _page_titles(DocOutline.from_raw_docs(RAW, order=FASTAPI_URLS)) == expected


def test_section_ids_are_contiguous_and_start_at_one():
    outline = DocOutline.from_raw_docs(RAW, order=FASTAPI_URLS)
    assert sorted(outline.valid_ids) == list(range(1, len(outline) + 1))


def test_outline_uses_scrape_time_positions_when_no_order_is_given(tmp_path):
    pages = {"a.md": ("Alpha", 2), "b.md": ("Bravo", 0), "c.md": ("Charlie", 1)}
    manifest = {}
    for fname, (title, pos) in pages.items():
        (tmp_path / fname).write_text(f"# {title}\n\n## Section\n\ntext\n")
        manifest[fname] = {"url": f"https://x/{fname}", "scraped_at": "2026-01-01T00:00:00+00:00", "title": title, "position": pos}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert _page_titles(DocOutline.from_raw_docs(tmp_path)) == ["Bravo", "Charlie", "Alpha"]


def test_explicit_order_overrides_recorded_positions(tmp_path):
    manifest = {}
    for fname, (title, pos) in {"a.md": ("Alpha", 0), "b.md": ("Bravo", 1)}.items():
        (tmp_path / fname).write_text(f"# {title}\n\n## S\n\nt\n")
        manifest[fname] = {"url": f"https://x/{fname}", "scraped_at": "2026-01-01T00:00:00+00:00", "title": title, "position": pos}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert _page_titles(DocOutline.from_raw_docs(tmp_path, order=["https://x/b.md", "https://x/a.md"])) == ["Bravo", "Alpha"]