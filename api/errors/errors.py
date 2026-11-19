from docker.errors import DockerException
from fastapi import FastAPI,Request,status
from fastapi.responses import JSONResponse

from api.services.course_store import CourseNotFound
from api.services.reasoning_models.errors.model_errors import MissingApiKey,ModelNotConfigured
from exercises.case_runner import HarnessError
from sandbox.image_builder import ImageBuildError

class ApiError(Exception):
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message:str):
        super().__init__(message)
        self.message=message

class NotFound(ApiError):
    status_code=status.HTTP_404_NOT_FOUND

class Invalid(ApiError):
    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT

class Locked(ApiError):
    status_code=status.HTTP_403_FORBIDDEN

class Conflict(ApiError):
    status_code=status.HTTP_409_CONFLICT

class Unavailable(ApiError):
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE


_RUNNER_DOWN = "The code runner is unavailable right now. Please try again."

def registry_error_handlers(app:FastAPI) ->None:
    def respond(code: int, message: str) -> JSONResponse:
        return JSONResponse({"detail": message}, status_code=code)

    @app.exception_handler(ApiError)
    def _api_error(_:Request,exc:ApiError):
        return respond(exc.status_code,exc.message)

    @app.exception_handler(ModelNotConfigured)
    def _no_model(_: Request, exc: ModelNotConfigured):
        return respond(status.HTTP_409_CONFLICT, "Choose a model in Settings first.")

    @app.exception_handler(MissingApiKey)
    def _no_key(_: Request, exc: MissingApiKey):
        return respond(
            status.HTTP_409_CONFLICT, f"Add your {exc.provider} API key in Settings first."
        )

    @app.exception_handler(CourseNotFound)
    def _course_not_found(_:Request,exc:CourseNotFound):
        return respond(status.HTTP_404_NOT_FOUND,"Course Not Found.")

    @app.exception_handler(HarnessError)
    def _harness(_: Request, exc: HarnessError):
        return respond(status.HTTP_503_SERVICE_UNAVAILABLE, _RUNNER_DOWN)

    @app.exception_handler(DockerException)
    def _docker(_: Request, exc: DockerException):
        return respond(status.HTTP_503_SERVICE_UNAVAILABLE,_RUNNER_DOWN)

    @app.exception_handler(ImageBuildError)
    def _image(_: Request, exc: ImageBuildError):
        return respond(status.HTTP_503_SERVICE_UNAVAILABLE, "The course environment could not be prepared.")

    

