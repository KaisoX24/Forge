from pydantic import BaseModel
from enum import Enum

class ExecutionError(Enum):
    TIMEOUT='timeout'
    RUNTIME_ERROR='runtime_error'
    DAEMON_UNAVAILABLE='daemon_unavailable'
    IMAGE_NOT_FOUND='image_not_found'
    UNKOWN='unknown'

class ExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    error_type: ExecutionError | None = None

class RetrievedDocument(BaseModel):
    content:str
    metadata:dict
    distance:float