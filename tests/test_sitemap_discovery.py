
import pytest

from ingestion.discovery.sitemap_parser import (
    SitemapParseError,
    parse_sitemap,
)
from ingestion.discovery.sitemap_discovery import (
    SitemapDiscovery,
    SitemapDiscoveryError,
    SitemapNotFoundError,
)


def test_parse_urlset():
    xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://example.com/docs/</loc>
        </url>
        <url>
            <loc>https://example.com/docs/tutorial/</loc>
        </url>
    </urlset>
    """

    result = parse_sitemap(xml)

    assert result.urls == [
        "https://example.com/docs/",
        "https://example.com/docs/tutorial/",
    ]
    assert result.sitemaps == []


def test_parse_sitemap_index():
    xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap>
            <loc>https://example.com/sitemap-docs.xml</loc>
        </sitemap>
        <sitemap>
            <loc>https://example.com/sitemap-api.xml</loc>
        </sitemap>
    </sitemapindex>
    """

    result = parse_sitemap(xml)

    assert result.urls == []
    assert result.sitemaps == [
        "https://example.com/sitemap-docs.xml",
        "https://example.com/sitemap-api.xml",
    ]


def test_parse_invalid_xml():
    with pytest.raises(SitemapParseError):
        parse_sitemap("<urlset><url></urlset>")


def test_parse_unsupported_root():
    with pytest.raises(SitemapParseError):
        parse_sitemap("<html></html>")


def test_rejects_entity_declarations():
    xml = """
    <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <urlset></urlset>
    """

    with pytest.raises(SitemapParseError):
        parse_sitemap(xml)


def test_extract_sitemap_directives():
    robots = """
    User-agent: *
    Allow: /

    Sitemap: https://example.com/sitemap.xml
    Sitemap: https://example.com/sitemap-api.xml
    """

    result = SitemapDiscovery._extract_sitemap_urls(robots)

    assert result == [
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap-api.xml",
    ]


def test_recursive_sitemap_discovery():
    responses = {
        "https://example.com/robots.txt": """
            User-agent: *
            Sitemap: https://example.com/sitemap.xml
        """,
        "https://example.com/sitemap.xml": """
            <sitemapindex>
                <sitemap>
                    <loc>https://example.com/docs.xml</loc>
                </sitemap>
                <sitemap>
                    <loc>https://example.com/api.xml</loc>
                </sitemap>
            </sitemapindex>
        """,
        "https://example.com/docs.xml": """
            <urlset>
                <url>
                    <loc>https://example.com/docs/intro</loc>
                </url>
            </urlset>
        """,
        "https://example.com/api.xml": """
            <urlset>
                <url>
                    <loc>https://example.com/api/reference</loc>
                </url>
            </urlset>
        """,
    }

    discovery = SitemapDiscovery(
        fetcher=lambda url: responses.get(url)
    )

    pages = discovery.discover("https://example.com/docs/")

    assert pages == [
        "https://example.com/docs/intro",
        "https://example.com/api/reference",
    ]


def test_falls_back_to_conventional_sitemap():
    responses = {
        "https://example.com/robots.txt": "User-agent: *\nDisallow:",
        "https://example.com/sitemap.xml": """
            <urlset>
                <url>
                    <loc>https://example.com/docs/intro</loc>
                </url>
            </urlset>
        """,
    }

    discovery = SitemapDiscovery(
        fetcher=lambda url: responses.get(url)
    )

    pages = discovery.discover("https://example.com/docs/")

    assert pages == ["https://example.com/docs/intro"]


def test_raises_when_no_sitemap_exists():
    discovery = SitemapDiscovery(
        fetcher=lambda url: None
    )

    with pytest.raises(SitemapNotFoundError):
        discovery.discover("https://example.com/docs/")


def test_prevents_recursive_sitemap_loops():
    sitemap = """
        <sitemapindex>
            <sitemap>
                <loc>https://example.com/sitemap.xml</loc>
            </sitemap>
        </sitemapindex>
    """

    responses = {
        "https://example.com/robots.txt": (
            "Sitemap: https://example.com/sitemap.xml"
        ),
        "https://example.com/sitemap.xml": sitemap,
    }

    calls = []

    def fake_fetch(url):
        calls.append(url)
        return responses.get(url)

    discovery = SitemapDiscovery(fetcher=fake_fetch)

    assert discovery.discover("https://example.com/docs/") == []
    assert calls.count("https://example.com/sitemap.xml") == 1


def test_rejects_invalid_docs_url():
    discovery = SitemapDiscovery(fetcher=lambda url: None)

    with pytest.raises(ValueError):
        discovery.discover("ftp://example.com/docs/")
