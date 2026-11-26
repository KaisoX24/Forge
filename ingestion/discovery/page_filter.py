from dataclasses import dataclass,field
from urllib.parse import unquote,urlsplit

from ingestion.discovery.url_normalizer import normalize_url

@dataclass
class ExcludedPage:
    url:str
    reason:str

@dataclass
class PageFilterResult:
    pages: list[str] = field(default_factory=list)
    excluded: list[ExcludedPage] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)

class PageFilter:
    "Filter discoverd URLs before ingestion"

    EXCLUDED_SEGMENTS = {
        "changelog": "Changelog",
        "changes": "Change history",
        "release": "Release information",
        "releases": "Release information",
        "release-notes": "Release notes",
        "blog": "Blog",
        "news": "News",
        "archive": "Archive",
        "archives": "Archive",
        "tags": "Tag listing",
        "categories": "Category listing",
        "search": "Search page",
        "feed": "Feed",
        "feeds": "Feed",
    }

    def filter(self,urls:list[str],docs_url:str) -> PageFilterResult:
        """
        Filter URLs against the documentation site's origin
        and configured excluded path segments.
        """

        result=PageFilterResult()

        docs_normalized=normalize_url(docs_url)
        docs_parsed=urlsplit(docs_normalized)

        seen:set[str]=set()

        for ori_url in urls:
            try:
                normalized=normalize_url(ori_url)
                parsed=urlsplit(normalized)
            except ValueError:
                result.excluded.append(
                    ExcludedPage(
                        url=ori_url,
                        reason="Invalid or unsupported URL",
                    )
                )
                continue

            if not self._same_origin(docs_parsed, parsed):
                result.excluded.append(
                    ExcludedPage(
                        url=ori_url,
                        reason="Outside documentation origin",
                    )
                )
                continue

            if normalized in seen:
                result.duplicates.append(ori_url)
                continue

            seen.add(normalized)

            reason = self._get_exclusion_reason(parsed.path)

            if reason:
                result.excluded.append(
                    ExcludedPage(
                        url=ori_url,
                        reason=reason,
                    )
                )
                continue

            result.pages.append(normalized)

        return result

    @staticmethod
    def _same_origin(reference, candidate) -> bool:
        "Compare scheme, hostname and effective port."

        def effective_port(parsed):
            if parsed.port is not None:
                return parsed.port

            return 443 if parsed.scheme == "https" else 80

        try:
            return (
                reference.scheme == candidate.scheme
                and reference.hostname == candidate.hostname
                and effective_port(reference) == effective_port(candidate)
            )
        except ValueError:
            return False

    def _get_exclusion_reason(self, path: str) -> str | None:
        """Check URL path segments against exclusion rules."""

        segments = [
            unquote(segment).lower()
            for segment in path.split("/")
            if segment
        ]

        for segment in segments:
            normalized_segment = segment.rsplit(".", 1)[0]

            reason = self.EXCLUDED_SEGMENTS.get(normalized_segment)

            if reason:
                return reason

        return None