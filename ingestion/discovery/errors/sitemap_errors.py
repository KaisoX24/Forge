class SitemapParseError(ValueError):
    """Invalid or unsupported sitemap XML."""

class SitemapDiscoveryError(RuntimeError):
    """Base exception for sitemap discovery failures."""


class SitemapNotFoundError(SitemapDiscoveryError):
    """No usable sitemap could be discovered."""