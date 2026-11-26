
import pytest

from ingestion.discovery.url_normalizer import (
    normalize_url,
    normalize_urls,
)

from ingestion.discovery.page_filter import PageFilter


def test_normalize_removes_fragment():
    assert normalize_url(
        "https://example.com/docs/tutorial#installation"
    ) == "https://example.com/docs/tutorial/"


def test_normalize_host_and_default_port():
    assert normalize_url(
        "HTTPS://EXAMPLE.COM:443/docs/tutorial/"
    ) == "https://example.com/docs/tutorial/"


def test_normalize_preserves_path_case():
    assert normalize_url(
        "https://example.com/API/Reference"
    ) == "https://example.com/API/Reference/"


def test_normalize_preserves_query_parameters():
    assert normalize_url(
        "https://example.com/docs/?version=2"
    ) == "https://example.com/docs/?version=2"


def test_normalize_preserves_non_default_port():
    assert normalize_url(
        "https://example.com:8443/docs/"
    ) == "https://example.com:8443/docs/"


def test_normalize_urls_removes_duplicates():
    urls = [
        "https://example.com/docs/tutorial",
        "https://EXAMPLE.com/docs/tutorial/",
        "https://example.com/docs/tutorial#setup",
        "https://example.com/docs/advanced",
    ]

    result = normalize_urls(urls)

    assert result == [
        "https://example.com/docs/tutorial/",
        "https://example.com/docs/advanced/",
    ]


def test_normalize_rejects_unsupported_scheme():
    with pytest.raises(ValueError):
        normalize_url("ftp://example.com/docs/")


def test_normalize_rejects_invalid_url():
    with pytest.raises(ValueError):
        normalize_url("not-a-url")


def test_filter_excludes_changelog():
    page_filter = PageFilter()

    result = page_filter.filter(
        [
            "https://example.com/docs/tutorial/",
            "https://example.com/docs/changelog/",
        ],
        "https://example.com/docs/",
    )

    assert len(result.pages) == 1
    assert len(result.excluded) == 1
    assert result.excluded[0].reason == "Changelog"


def test_filter_excludes_release_notes():
    page_filter = PageFilter()

    result = page_filter.filter(
        [
            "https://example.com/docs/release-notes/",
            "https://example.com/docs/tutorial/",
        ],
        "https://example.com/docs/",
    )

    assert len(result.pages) == 1
    assert result.excluded[0].reason == "Release notes"


def test_filter_excludes_external_urls():
    page_filter = PageFilter()

    result = page_filter.filter(
        [
            "https://example.com/docs/tutorial/",
            "https://github.com/example/project",
        ],
        "https://example.com/docs/",
    )

    assert len(result.pages) == 1
    assert result.excluded[0].reason == "Outside documentation origin"


def test_filter_removes_duplicates():
    page_filter = PageFilter()

    result = page_filter.filter(
        [
            "https://example.com/docs/tutorial",
            "https://example.com/docs/tutorial/",
            "https://example.com/docs/advanced/",
        ],
        "https://example.com/docs/",
    )

    assert len(result.pages) == 2
    assert len(result.duplicates) == 1


def test_filter_preserves_legitimate_history_content():
    page_filter = PageFilter()

    result = page_filter.filter(
        [
            "https://example.com/docs/history-of-python/",
            "https://example.com/docs/tutorial/",
        ],
        "https://example.com/docs/",
    )

    assert len(result.pages) == 2
    assert result.excluded == []


def test_filter_excludes_invalid_urls():
    page_filter = PageFilter()

    result = page_filter.filter(
        [
            "javascript:alert(1)",
            "https://example.com/docs/tutorial/",
        ],
        "https://example.com/docs/",
    )

    assert len(result.pages) == 1
    assert len(result.excluded) == 1
