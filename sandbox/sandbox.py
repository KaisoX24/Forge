from models.data_models import ExecutionResult,ExecutionError
from threading import Event,Thread
from .container_pool import ContainerPool,Container
import psutil

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
            container:Container = self.pool.get_container()

            worker_thread = Thread(target=worker, daemon=True)
            worker_thread.start()

            completed_in_time = finished_event.wait(self.timeout_seconds)

            if not completed_in_time:
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
    try:
        available_gb = psutil.virtual_memory().available / (1024**3)
        pool_size = max(1, min(10, int(available_gb / 0.5)))
    except Exception:
        pool_size = 3
    print(pool_size)
    user=input("Enter code:\n")
    with ContainerPool(pool_size=pool_size) as pool:
        run=SandBox(pool=pool,code=user).run_code()
    print(run)

