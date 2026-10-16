import asyncio
from pathlib import Path
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.models import CrawlResult
import json
from datetime import datetime,timezone

class DocScraper:
    def __init__(self, output_dir: Path = Path(__file__).parent / "raw_docs", css_selector: str = "article"):
        self.output_dir = Path(output_dir)
        self.manifest_path=self.output_dir/'manifest.json'
        self.css_selector = css_selector
        self.md_generator = DefaultMarkdownGenerator()
        self.config = CrawlerRunConfig(css_selector=self.css_selector,
                                       stream=True,
                                       cache_mode=CacheMode.BYPASS,
                                       markdown_generator=self.md_generator
                                       )
        self.crawler = AsyncWebCrawler()
        

    def _url_to_filename(self, url: str) -> str:
        path = url.replace("https://", "").replace("http://", "").replace(".com","")
        path = path.strip('/')
        filename = path.replace('/', '_').replace('-', '_') + '.md'
        return filename

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

    def _record_metadata(self, manifest: dict, url: str, filename: str, result: CrawlResult) -> None:
        manifest[filename] = {
            "url": url,
            "scraped_at":datetime.now(timezone.utc).isoformat(),
            "title":self._extract_title(result.markdown),
        }

    def _write_manifest(self, manifest: dict) -> None:
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    async def scrape_all(self, urls: list[str]) -> dict:
        succeeded = []
        failed = []
        manifest={}

        async with self.crawler:
            results:list[CrawlResult] = await self.crawler.arun_many(
                urls=urls,
                config=self.config
            )
            async for res in results:
                if res.success and res.markdown:
                    filename=self._url_to_filename(res.url)
                    self._save_document(res.markdown, res.url,filename)
                    self._record_metadata(manifest,res.url,filename,res)
                    succeeded.append(res.url)
                else:
                    reason = res.error_message if res.success else "empty or missing content"
                    print("Failed:", res.url, "-", reason)
                    failed.append({"url": res.url, "reason": reason})
        self._write_manifest(manifest)
        return {"succeeded": succeeded, "failed": failed}
    

    def run(self, urls: list[str]) -> dict:
        return asyncio.run(self.scrape_all(urls))

if __name__=="__main__":
    scrapper=DocScraper()
    scrapper.run(["https://fastapi.tiangolo.com/python-types/"])
