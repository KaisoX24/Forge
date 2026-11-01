import pytest
from docker.errors import APIError, ImageNotFound

from models.data_models import EnvironmentSpec
from sandbox.environment import render_dockerfile
from sandbox.image_builder import ImageBuildError, ensure_image


class FakeImages:
    def __init__(self, existing=(), build_error=None):
        self.existing, self.build_error, self.builds = set(existing), build_error, []

    def get(self, tag):
        if tag not in self.existing:
            raise ImageNotFound(tag)

    def build(self, **kwargs):
        if self.build_error:
            raise self.build_error
        self.builds.append(kwargs)
        self.existing.add(kwargs["tag"])


class FakeClient:
    def __init__(self, **kw):
        self.images = FakeImages(**kw)


SPEC = EnvironmentSpec(packages={"fastapi": "0.115.0"})


def test_existing_image_is_reused_without_building():
    client = FakeClient(existing={SPEC.image_tag})
    assert ensure_image(SPEC, client) == SPEC.image_tag
    assert client.images.builds == []


def test_missing_image_is_built_once_from_the_rendered_dockerfile():
    client = FakeClient()
    ensure_image(SPEC, client)
    ensure_image(SPEC, client)
    assert len(client.images.builds) == 1
    build = client.images.builds[0]
    assert build["tag"] == SPEC.image_tag
    assert build["fileobj"].getvalue().decode() == render_dockerfile(SPEC)


def test_build_failure_becomes_image_build_error():
    client = FakeClient(build_error=APIError("boom"))
    with pytest.raises(ImageBuildError):
        ensure_image(SPEC, client)