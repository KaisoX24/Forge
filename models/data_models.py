from pydantic import BaseModel,Field
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

class Module(BaseModel):
    title:str=Field(description="The title of the current learning Module")
    objectives:list[str]=Field(
        description="What the learner should be able to understand or do after completing the module."
    )
    documentation_requirements: list[str] = Field(
        description=(
            "Specific framework or technology information that must be "
            "verified from the documentation before generating this module."
        )
    )

class Curriculum(BaseModel):
    modules:list[Module]=Field(
        description="The ordered learning modules for the course."
    )