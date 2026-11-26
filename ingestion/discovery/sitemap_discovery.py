from __future__ import annotations

import gzip
import io
import urllib.error
import urllib.parse
import urllib.request

from collections.abc import Callable

from ingestion.discovery.errors.sitemap_errors import (
    SitemapParseError,SitemapDiscoveryError,SitemapNotFoundError
)
from ingestion.discovery.sitemap_parser import parse_sitemap


#Constants
TextFetcher = Callable[[str], str | None]


MAX_RESPONSE_SIZE = 10 * 1024 * 1024
DEFAULT_TIMEOUT = 15

SITEMAP_CANDIDATES = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
)

def fetch_text(url:str,timeout:float=DEFAULT_TIMEOUT) -> str|None:
    """Fetch a text resource, returning None for HTTP 404."""

    request=urllib.request.Request(
        url,
        headers={
            "User-Agent": "Forge-Documentation-Discovery/1.0",
            "Accept": "text/plain, application/xml, text/xml, */*"
        }
    )

    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            final_url=urllib.parse.urlsplit(response.geturl())
            original_url=urllib.parse.urlsplit(url)

            if (final_url.scheme not in ('http','https')
                or final_url.hostname != original_url.hostname):

                raise SitemapDiscoveryError(
                    f"Unexpected redirect destination: {response.geturl()}"
                )

            data=response.read(MAX_RESPONSE_SIZE+1)

            if len(data)>MAX_RESPONSE_SIZE:
                raise SitemapDiscoveryError(
                    f"Response exceeds maximum size: {url}"
                )

            if url.lower().endswith(".gz") or data.startswith(b"\x1f\x8b"):
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
                        data=gz.read(MAX_RESPONSE_SIZE+1)
                        
                except OSError as exc:
                    raise SitemapDiscoveryError(
                        f"Invalid gzip sitemap: {url}"
                    ) from exc

                if len(data) > MAX_RESPONSE_SIZE:
                    raise SitemapDiscoveryError(
                        f"Decompressed sitemap exceeds maximum size: {url}"
                    )

            return data.decode("utf-8-sig")

    except urllib.error.HTTPError as exc:
        if exc.code==404: return None

        raise SitemapDiscoveryError(
            f"HTTP {exc.code} while fetching {url}"
        ) from exc

    except (urllib.error.URLError, TimeoutError) as exc:
        raise SitemapDiscoveryError(
            f"Could not fetch {url}: {exc}"
        ) from exc

class SitemapDiscovery:
    def __init__(
        self,
        fetcher: TextFetcher = fetch_text,
        *,
        max_sitemaps: int = 50,
        max_pages: int = 5000,
        max_depth: int = 5,
    ):
        self.fetcher = fetcher
        self.max_sitemaps = max_sitemaps
        self.max_pages = max_pages
        self.max_depth = max_depth

    def discover(self,docs_url:str) ->list[str]:
        "Discover documentation page URLs from a site's sitemaps."

        parsed=urllib.parse.urlsplit(docs_url)

        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("docs_url must be a valid HTTP(S) URL")

        origin = f"{parsed.scheme}://{parsed.netloc}"

        robots_url=urllib.parse.urljoin(origin,'/robots.txt')
        robots_content=self.fetcher(robots_url)

        sitemap_urls=self._extract_sitemap_urls(robots_content or "")

        pages = self._crawl_sitemaps(
            sitemap_urls,
            allowed_host=parsed.hostname,
        )

        if pages is None:
            candidates = [
                urllib.parse.urljoin(origin, path)
                for path in SITEMAP_CANDIDATES
            ]

            pages = self._crawl_sitemaps(candidates,allowed_host=parsed.hostname)

        if pages is None:
            raise SitemapNotFoundError(
                f"No usable sitemap found for {docs_url}"
            )

        return pages

    @staticmethod
    def _extract_sitemap_urls(robots_content:str) ->list[str]:
        "Extract Sitemap directives from robots.txt."

        urls=[]

        for line in robots_content.splitlines():
            line=line.strip()

            if not line or ':' not in line:
                continue

            directive,value=line.split(':',1)

            if directive.strip().lower()=='sitemap':
                if value.strip():
                    urls.append(value.strip())

        return urls

    def _crawl_sitemaps(self,sitemap_urls: list[str],*,allowed_host:str) ->list[str]|None:
        "Recursively traverse sitemap indexes."

        visited:set[str]=set()
        pages:list[str]=[]
        found_sitemap=False

        def visit(url:str,depth:int)->None:
            nonlocal found_sitemap

            if url in visited: return

            if depth>self.max_depth:
                raise SitemapDiscoveryError(
                    f"Maximum sitemap recursion depth exceeded: {url}"
                )

            if len(visited) >= self.max_sitemaps:
                raise SitemapDiscoveryError(
                    "Maximum sitemap count exceeded."
                )

            visited.add(url)

            parsed=urllib.parse.urlsplit(url)

            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname != allowed_host
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise SitemapDiscoveryError(
                    f"Untrusted sitemap URL: {url}"
                )

            content=self.fetcher(url)

            if content is None: return

            found_sitemap=True

            try:
                result=parse_sitemap(content)
            except SitemapParseError as exc:
                raise SitemapDiscoveryError(
                    f"Invalid sitemap at {url}: {exc}"
                ) from exc

            if result.sitemaps:
                for child_url in result.sitemaps:
                    visit(child_url,depth+1)

            for page_url in result.urls:
                if len(pages) >= self.max_pages:
                    raise SitemapDiscoveryError(
                        "Maximum discovered page count exceeded."
                    )

                pages.append(page_url)

        for url in sitemap_urls:
            visit(url,depth=0)

        return pages if found_sitemap else None
    