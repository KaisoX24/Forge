from dataclasses import dataclass
from xml.etree import ElementTree as ET
from ingestion.discovery.errors.sitemap_errors import SitemapParseError

@dataclass
class SitemapDocument:
    urls: list[str]
    sitemaps: list[str]

def _local_name(tag: str) -> str:
    """Remove an XML namespace from a tag."""
    return tag.rsplit("}", 1)[-1].lower()

def parse_sitemap(content:str|bytes) -> SitemapDocument:
    """
    Parse a sitemap URL set or sitemap index.
    URL sets return page URLs.
    Sitemap indexes return child sitemap URLs.
    """

    if isinstance(content,str):
        content=content.encode('utf-8')

    # Reject DTD and entity declarations in untrusted XML.
    upper_content=content.upper()

    if b"<!DOCTYPE" in upper_content or b"<!ENTITY" in upper_content:
        raise SitemapParseError("DTD and entity declarations are not allowed.")

    try:
        root=ET.fromstring(content)
    except ET.ParseError as exc:
        raise SitemapParseError(
            f"Could not parse sitemap XML: {exc}"
        ) from exc

    root_type=_local_name(root.tag)

    if root_type not in {"urlset", "sitemapindex"}:
        raise SitemapParseError(
            f"Unsupported sitemap root element: {root_type}"
        )

    urls:list[str]=[]
    sitemaps:list[str]=[]

    for entry in root:
        location=next(
            (
                child.text.strip()
                for child in entry
                if _local_name(child.tag)=='loc' and child.text
            ),
            None,
        )

        if not location: continue

        if root_type=='urlset':
            urls.append(location)
        else:
            sitemaps.append(location)

    return SitemapDocument(
        urls=urls,
        sitemaps=sitemaps
    )