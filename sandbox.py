import docker
from docker.errors import APIError,ImageNotFound
from docker.models.containers import Container
from models.data_models import ExecutionResult,ExecutionError
from threading import Event,Thread
from queue import Queue
import logging

class ContainerPool:
    def __init__(self, pool_size: int, image: str = "python:3.11-slim"):
        self.pool_size = pool_size
        self.image = image
        self.client = docker.from_env()
        self.queue = Queue(maxsize=pool_size)

        self._create_container()


    def _create_container(self,replace:bool=False):
        pools=self.pool_size if not(replace) else 1
        for _ in range(pools):
            container:Container=self.client.containers.run(
                image='python:3.11-slim',
                    command=["sleep" ,"infinity"],
                    detach=True,
                    mem_limit="256m",
                    nano_cpus=500_000_000,
                    pids_limit=50,
                    network_disabled=True,
                    user='1000:1000',
                    cap_drop=['all']
                )

            self.queue.put(container)
            
    def get_container(self):
        return self.queue.get()

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

class SandBox:
    def __init__(self, pool: ContainerPool, code: str, timeout_seconds: int = 15):
        self.pool = pool
        self.code = code
        self.timeout_seconds = timeout_seconds

    def sandbox_instance(self) -> ExecutionResult:

        container = None
        finished_event = Event()
        exec_outcome = {}

        def worker():
            try:
                exit_code, output = container.exec_run(
                    cmd=["python3", "-c", self.code]
                )
                exec_outcome["exit_code"] = exit_code
                exec_outcome["output"] = output
            except Exception as e:
                exec_outcome["error"] = e
            finally:
                finished_event.set()

        try:
            container = self.pool.get_container()

            worker_thread = Thread(target=worker, daemon=True)
            worker_thread.start()

            completed_in_time = finished_event.wait(self.timeout_seconds)

            if not completed_in_time:
                # don't wait on worker_thread — it may still be running forever
                return ExecutionResult(
                    success=False,
                    stderr=f"Execution exceeded the {self.timeout_seconds}s time limit and was terminated.",
                    error_type=ExecutionError.TIMEOUT
                )

            if "error" in exec_outcome:
                raise exec_outcome["error"]

            result = exec_outcome["exit_code"]
            output = exec_outcome["output"]

            if result != 0:
                return ExecutionResult(success=False, stderr=output, error_type=ExecutionError.RUNTIME_ERROR)

            return ExecutionResult(success=True, stdout=output)

        except Exception as e:
            return ExecutionResult(success=False, stderr=str(e), error_type=ExecutionError.UNKOWN)

        finally:
            if container is not None:
                if finished_event.is_set():
                    self.pool.return_container(container)
                else:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass
                    self.pool.replace_container()

    def run_code(self) ->str:
        result=self.sandbox_instance()
        if result.success:
            return result.stdout
        return result.stderr
    
if __name__=='__main__':
    user=input("Enter code:\n")
    run=SandBox(pool=ContainerPool(pool_size=3),code=user)
    print(run)

