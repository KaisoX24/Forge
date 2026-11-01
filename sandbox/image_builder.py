from __future__ import annotations
import io
import logging
import docker
from docker.errors import APIError,BuildError,ImageNotFound
from models.data_models import EnvironmentSpec
from sandbox.environment import render_dockerfile

logger=logging.getLogger(__name__)

class ImageBuildError(RuntimeError):
    "The sandbox image for a course could not be built."

def ensure_image(spec:EnvironmentSpec,client:docker.DockerClient|None=None) ->str:
    "Creates a docker image based on the framework requirement"
    client=client or docker.from_env()
    tag=spec.image_tag
    try:
        client.images.get(tag)
        return tag
    except ImageNotFound:
        pass

    try:
        client.images.build(
            fileobj=io.BytesIO(render_dockerfile(spec).encode('utf-8')),
            tag=tag,rm=True,labels={"forge.env_id":spec.env_id}
        )
    except (BuildError,APIError) as exc:
        raise ImageBuildError(f"could not build {tag}: {exc}") from exc

    return tag