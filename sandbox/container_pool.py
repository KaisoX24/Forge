import docker
from docker.errors import APIError,ImageNotFound
from docker.models.containers import Container
from queue import Queue
import logging
import atexit
from models.data_models import EnvironmentSpec
from sandbox.image_builder import ensure_image

class ContainerPool:
    def __init__(self, pool_size: int,spec:EnvironmentSpec|None=None):
        self.pool_size = pool_size
        self.spec=spec or EnvironmentSpec()
        self.client = docker.from_env()
        self.image=ensure_image(self.spec,self.client)
        self.queue = Queue(maxsize=pool_size)

        self._create_container()
        atexit.register(self.shutdown)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.shutdown()

    def _create_container(self,replace:bool=False):
        pools=self.pool_size if not(replace) else 1
        for _ in range(pools):
            container:Container=self.client.containers.run(
                image=self.image,
                command=["sleep" ,"infinity"],
                detach=True,
                mem_limit=f"{self.spec.memory_mb}m",
                nano_cpus=500_000_000,
                pids_limit=50,
                network_disabled=True,
                user='1000:1000',
                cap_drop=['all'],
                read_only=True,
                tmpfs={"/tmp": "size=16m,mode=1777,noexec"},
                environment={"HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1"}
            )

            self.queue.put(container)
            
    def get_container(self):
        return self.queue.get()

    def reset(self,container:Container) -> bool:
        "Wipe space and confirm nothing is running"
        try:
            code,_=container.exec_run(["find", "/tmp", "-mindepth", "1", "-delete"])
            if code!=0:
                return False
            return len(container.top().get("Processes") or []) <= 1
        except Exception:
            return False

    def return_container(self, container:Container):
        self.queue.put(container)

    def replace_container(self):
        try:
            self._create_container(replace=True)
        except (APIError,ImageNotFound) as e:
            logging.error(f"Failed to replace container after timeout: {e}")

    def shutdown(self):
        while not self.queue.empty():
            container:Container=self.queue.get()
            try:
                container.remove(force=True)
            except Exception:
                pass
