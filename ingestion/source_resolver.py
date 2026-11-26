from pydantic import HttpUrl,ValidationError,TypeAdapter

from models.course import CourseSources
from sandbox.pypi import PyPI

class SourceResolutionError(Exception):
    """Base exception for source resolution failures."""


class PackageNotFoundError(SourceResolutionError):
    """Package does not exist on PyPI."""


class DocumentationURLNotFoundError(SourceResolutionError):
    """No usable documentation URL was found."""

HTTP_URL_ADAPTER=TypeAdapter(HttpUrl)


class SourceResolver:

    DOC_LABELS = (
        "documentation",
        "docs",
        "documentation site",
        "read the docs",
        "api documentation",
    )

    def __init__(self,pypi:PyPI|None=None):
        self.pypi=pypi or PyPI()

    def resolve(self,name:str,docs_url:str|None=None,
                selector:str|None=None) -> CourseSources:

        name=name.strip()

        if not name:
            raise ValueError("Package name cannot be empty")

        # If url provided return CourseSources
        if docs_url:
            return CourseSources(
                name=name,
                docs_url=docs_url,
                selector=selector
            )

        # Query PyPi
        project=self.pypi.project(name)

        if project is None:
            raise PackageNotFoundError(
                f"Package '{name}' was not found on PyPI."
            )

        info=project.get('info') or {}

        resolved_name=info.get('name') or name

        docs_url=self._find_documentation_url(info)

        if docs_url is None:
            raise DocumentationURLNotFoundError(
                f"No documentation URL found for '{resolved_name}'. "
                "Please provide one manually."
            )

        return CourseSources(
            name=resolved_name,
            docs_url=docs_url,
            selector=selector
        )

    def _find_documentation_url(self,info:dict) -> str | None:
        project_urls=info.get('project_urls') or {}

        normalized_urls={
            label.strip().lower():url
            for label,url in project_urls.items()
            if isinstance(label,str) and isinstance(url,str)
        }

        for label in self.DOC_LABELS:
            url=normalized_urls.get(label)

            if self._is_valid_url(url):
                return url

        candidates = [
            info.get("home_page"),
            normalized_urls.get("homepage"),
            normalized_urls.get("home"),
        ]

        for url in candidates:
            if self._is_valid_url(url):
                return url   

        return None

    @staticmethod
    def _is_valid_url(url:str|None) ->bool:
        if not url:
            return False

        try:
            HTTP_URL_ADAPTER.validate_python(url)
            return True
        except ValidationError:
            return False
        