import docker
from docker.errors import APIError,ImageNotFound
from docker.models.containers import Container
from models.data_models import ExecutionResult,ExecutionError

from threading import Event,Thread

class SandBox:
    def __init__(self,code:str,timeout_seconds:int=15):
        self.client=docker.from_env()
        self.code=code
        self.timeout_seconds=timeout_seconds


    def sandbox_instance(self) ->ExecutionResult:
        container=None
        finished_event=Event()
        timeout_flag=Event()

        def watchdog(container_ref:Container):
            if not finished_event.wait(self.timeout_seconds):
                try:
                    container_ref.kill()
                except Exception:
                    pass
                timeout_flag.set()
        try:
            container=self.client.containers.run(
                image='python:3.11-slim',
                command=["python3","-c",self.code],
                detach=True,
                mem_limit="256m",
                nano_cpus=500_000_000,
                pids_limit=50
            )

            watchdog_thread=Thread(
                target=watchdog,args=(container,),daemon=True
            )
            watchdog_thread.start()

            result=container.wait().get('StatusCode')
            output=container.logs()

            finished_event.set()
            watchdog_thread.join()

            if timeout_flag.is_set():
                return ExecutionResult(
                    success=False,
                    stdout=output,
                    stderr=f"Execution exceeded the {self.timeout_seconds}s time limit and was terminated.",
                    error_type=ExecutionError.TIMEOUT
                )

            if result!=0:
                return ExecutionResult(
                    success=False,
                    stderr=output,
                    error_type=ExecutionError.RUNTIME_ERROR
                            )

            return ExecutionResult(
                success=True,
                stdout=output
            )

        except ImageNotFound as e:
            return ExecutionResult(
                success=False,
                stderr=e.explanation,
                error_type=ExecutionError.IMAGE_NOT_FOUND
            )

        except APIError as e:
            return ExecutionResult(
                success=False,
                stderr=e.explanation,
                error_type=ExecutionError.DAEMON_UNAVAILABLE
            )
        
        except Exception as e:
            return ExecutionResult(
                success=False,
                stderr=str(e),
                error_type=ExecutionError.UNKOWN
            )

        finally:
            if container is not None:
                container.remove()

    def run_code(self) ->str:
        result=self.sandbox_instance()
        if result.success:
            return result.stdout
        return result.stderr
    
if __name__=='__main__':
    user=input("Enter code:\n").strip()
    run=SandBox(user).run_code()
    print(run)

