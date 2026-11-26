import asyncio
from urllib.parse import unquote,urlsplit
from pathlib import Path
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.models import CrawlResult
import json
from datetime import datetime,timezone
import re

from models.course import CourseSources


class DocScraper:
    def __init__(self,output_dir:Path=Path(__file__).parent.parent/"raw_docs",css_selector:str="article"
    ):
        self.base_dir = Path(output_dir)
        self.output_dir = self.base_dir
        self.css_selector = css_selector
        self.md_generator = DefaultMarkdownGenerator()
        self.config = self._build_config()
        self.crawler = AsyncWebCrawler()

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug:
            raise ValueError(f"Cannot build a folder name from: {name!r}")
        return slug

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / "manifest.json"
    
    
    def _build_config(self, selector: str | None = None) -> CrawlerRunConfig:
        return CrawlerRunConfig(
            css_selector=selector or self.css_selector,
            stream=True,
            cache_mode=CacheMode.BYPASS,
            markdown_generator=self.md_generator,
        )

    def _url_to_filename(self, url: str) -> str:
        path = unquote(urlsplit(url).path).strip("/")
        if path.endswith((".html", ".htm")):
            path = path.rsplit(".", 1)[0]
        name = path.replace("/", "__") or "index"
        return f"{name}.md"

    def _extract_title(self, markdown: str) -> str | None:
        first_line = markdown.strip().split("\n", 1)[0]
        if first_line.startswith("# "):
            title = first_line[2:].split("[¶]")[0].strip()
            return title
        return None

    def _save_document(self, text: str, url: str,filename:str) -> bool:
        try:
            self.output_dir.mkdir(exist_ok=True, parents=True)
            md_file = self.output_dir / filename
            md_file.write_text(text, encoding='utf-8')  
            return True
        except Exception as e:
            print(f"Exception occurred while saving {url}: {e}")
            return False

    def _record_metadata(self, manifest: dict, url: str, filename: str, result: CrawlResult,position:int) -> None:
        manifest[filename] = {
            "url": url,
            "scraped_at":datetime.now(timezone.utc).isoformat(),
            "title":self._extract_title(result.markdown),
            "position":position
        }

    def _write_manifest(self, manifest: dict) -> None:
        self.output_dir.mkdir(exist_ok=True,parents=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    async def scrape_all(self, urls: list[str]) -> dict:
        succeeded = []
        failed = []
        manifest={}
        position_of={u.rstrip("/"): i for i, u in enumerate(urls)}
        async with self.crawler:
            results:list[CrawlResult] = await self.crawler.arun_many(
                urls=urls,
                config=self.config
            )
            async for res in results:
                if res.success and res.markdown:
                    filename=self._url_to_filename(res.url)
                    saved=self._save_document(res.markdown, res.url,filename)

                    if not saved:
                        failed.append({
                            'url':res.url,
                            'reason':"Failed to save document"
                        })
                        continue

                    self._record_metadata(manifest,res.url,filename,res,position_of.get(res.url.rstrip("/"),len(urls)))
                    succeeded.append(res.url)
                else:
                    reason = res.error_message if not res.success else "empty or missing content"
                    print("Failed:", res.url, "-", reason)
                    failed.append({"url": res.url, "reason": reason})
        self._write_manifest(manifest)
        return {"succeeded": succeeded, "failed": failed}

    async def scrape_sources(self,sources:CourseSources) ->dict:
        if not sources.page_list:
            raise ValueError("page_list is empty; discover and select pages first")

        self.output_dir=self.base_dir/self._slugify(sources.name)
        self.config=self._build_config(sources.selector)

        return await self.scrape_all([str(u) for u in sources.page_list])
    

    def run(self, urls: list[str]) -> dict:
        return asyncio.run(self.scrape_all(urls))

if __name__=="__main__":
    scrapper=DocScraper()
    scrapper.run(["https://fastapi.tiangolo.com/python-types/"])
