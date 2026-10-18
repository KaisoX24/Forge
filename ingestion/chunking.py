from pathlib import Path
from langchain_text_splitters import MarkdownTextSplitter,ExperimentalMarkdownSyntaxTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
import re
import hashlib
import json
import logging

class Chunker:
    def __init__(self, chunk_size: int = 2500, chunk_overlap: int = 200):
        self.header_splitter=ExperimentalMarkdownSyntaxTextSplitter(
            headers_to_split_on=[("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3"), ("####", "Header 4")],
            strip_headers=False,
        )
        self.char_splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            strip_whitespace=False,
        )

    def _merge_sections(self, docs:list[Document]):
        merged = []
        for d in docs:
            headers = {k: v for k, v in d.metadata.items() if k.startswith("Header")}
            if merged and merged[-1].metadata == headers:
                merged[-1].page_content += d.page_content
            else:
                merged.append(Document(page_content=d.page_content, metadata=headers))
        return merged
    
    def _get_anchor_for_chunk(self, metadata: dict) -> str | None:
        for lvl in ["Header 4", "Header 3", "Header 2", "Header 1"]:
            if lvl in metadata:
                return self._extract_anchor(metadata[lvl])
        return None

    def _extract_anchor(self, heading_text: str) -> str | None:
        match = re.search(r'\(https?://[^\s]+?(#[\w-]+)\s', heading_text)
        if match:
            return match.group(1)
        return None

    def _generate_chunk_id(self, source_file: str, anchor: str | None, index: int) -> str:
        raw = f"{source_file}::{anchor}::{index}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _load_manifest(self, raw_docs_dir: Path) -> dict:
        path = raw_docs_dir / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def chunk_document(self, markdown_text: str, source_file: str, manifest_entry: dict) -> list[Document]:
        sections = self._merge_sections(self.header_splitter.split_text(markdown_text))
        chunks = self.char_splitter.split_documents(sections)
        counters: dict[str, int] = {}
        for c in chunks:
            anchor = self._get_anchor_for_chunk(c.metadata) or ""
            idx = counters.get(anchor, 0)
            counters[anchor] = idx + 1
            c.metadata.update(
                url=manifest_entry["url"],
                scraped_at=manifest_entry["scraped_at"],
                source_file=source_file,
                anchor=anchor,
                chunk_id=self._generate_chunk_id(source_file, anchor, idx),
            )
        return chunks

    def chunk_directory(self, raw_docs_dir: Path) -> list[Document]:
        manifest = self._load_manifest(raw_docs_dir)
        loader = DirectoryLoader(path=raw_docs_dir, glob="**/*.md", loader_cls=TextLoader,
                                loader_kwargs={"encoding": "utf-8"})
        all_docs: list[Document] = []
        for doc in loader.lazy_load():
            filename = Path(doc.metadata["source"]).name
            entry = manifest.get(filename)
            if entry is None:
                logging.warning("Skipping %s: not in manifest.json", filename)
                continue
            all_docs.extend(self.chunk_document(doc.page_content, filename, entry))
        return all_docs
    
if __name__=='__main__':
    chunker=Chunker()
    print(f'Total Chunks: {len(chunker.chunk_directory(Path(__file__).parent/'raw_docs'))}')