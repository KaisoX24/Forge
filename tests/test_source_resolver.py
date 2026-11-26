import pytest

from ingestion.source_resolver import (
    SourceResolver,
    PackageNotFoundError,
    DocumentationURLNotFoundError,
)


class FakePyPI:
    def __init__(self, project):
        self._project = project
        self.calls = []

    def project(self, name):
        self.calls.append(name)
        return self._project


def test_resolves_documentation_from_pypi():
    pypi = FakePyPI({
        "info": {
            "name": "FastAPI",
            "project_urls": {
                "Documentation": "https://fastapi.tiangolo.com/",
                "Source": "https://github.com/fastapi/fastapi",
            },
        }
    })

    source = SourceResolver(pypi).resolve("fastapi")

    assert source.name == "FastAPI"
    assert str(source.docs_url) == "https://fastapi.tiangolo.com/"
    assert pypi.calls == ["fastapi"]


def test_manual_url_overrides_pypi():
    pypi = FakePyPI(None)

    source = SourceResolver(pypi).resolve(
        name="FastAPI",
        docs_url="https://custom.example.com/docs",
    )

    assert str(source.docs_url) == "https://custom.example.com/docs"
    assert pypi.calls == []


def test_docs_label_is_preferred_over_homepage():
    pypi = FakePyPI({
        "info": {
            "name": "Example",
            "home_page": "https://example.com",
            "project_urls": {
                "Documentation": "https://docs.example.com",
            },
        }
    })

    source = SourceResolver(pypi).resolve("example")

    assert str(source.docs_url) == "https://docs.example.com/"


def test_homepage_is_used_as_fallback():
    pypi = FakePyPI({
        "info": {
            "name": "Example",
            "home_page": "https://example.com",
            "project_urls": {},
        }
    })

    source = SourceResolver(pypi).resolve("example")

    assert str(source.docs_url) == "https://example.com/"


def test_unknown_package_raises_error():
    resolver = SourceResolver(FakePyPI(None))

    with pytest.raises(PackageNotFoundError):
        resolver.resolve("unknown-package")


def test_missing_documentation_url_raises_error():
    pypi = FakePyPI({
        "info": {
            "name": "Example",
            "project_urls": {},
        }
    })

    with pytest.raises(DocumentationURLNotFoundError):
        SourceResolver(pypi).resolve("example")


def test_selector_is_preserved():
    pypi = FakePyPI({
        "info": {
            "name": "Example",
            "project_urls": {
                "Documentation": "https://docs.example.com",
            },
        }
    })

    source = SourceResolver(pypi).resolve(
        "example",
        selector="article",
    )

    assert source.selector == "article"
