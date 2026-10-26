from pydantic import BaseModel,Field,field_validator,StringConstraints
from enum import Enum
import re
from typing import Annotated

_TITLE_PREFIX = re.compile(r"^\s*(module|lesson|unit)\s*\d+\s*[:.\-\u2013]\s*", re.I)

def _strip_title_prefix(title: str) -> str:
    # Cleans the title from cosmetic prefixs like module|lesson|unit
    previous = None
    while previous != title:
        previous = title
        title = _TITLE_PREFIX.sub("", title)
    return title.strip()

# Constraint for the text stored
Text=Annotated[str,StringConstraints(strip_whitespace=True,min_length=240)]
Objective = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=160)]
Requirement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=200)]

class ModuleOutline(BaseModel):
    # The outline stage only decides WHAT each module should cover.
    title: str = Field(min_length=3, max_length=80, description="Short, specific module title")
    section_ids: list[int] = Field(
        min_length=1,
        description="IDs of the documentation sections this module teaches",
    )

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        return _strip_title_prefix(v)



class ObjectivePlan(BaseModel):
    objective:Objective
    requirements:list[Requirement]=Field(min_length=1,max_length=2)


class CurriculumOutline(BaseModel):
    # Curriculum Outline that every curriculum would have
    modules: list[ModuleOutline] = Field(min_length=1, max_length=6)

class ModuleDetail(BaseModel):
    # Store the detail retaining to a module
    steps:list[ObjectivePlan]=Field(min_length=2,max_length=4)

class Module(BaseModel):
    # Handles whats stored in Module
    title:str=Field(description="The title of the current learning Module")
    steps:list[ObjectivePlan]=Field(
        description="Ordered lesson steps. Each has one objective and the docs facts needed to teach it."
    )
    source_sections: list[str] = Field(
        default_factory=list,
        description="Documentation sections (heading or permalink) this module is built from.",
    )

    @property
    def objectives(self) ->list[str]:
        return [step.objective for step in self.steps]

    @property
    def documentation_requirements(self)->list[str]:
        return [req for step in self.steps for req in step.requirements]

class Curriculum(BaseModel):
    # Stores the current Curriculum
    modules:list[Module]=Field(
        min_length=1,
        description="The ordered learning modules for the course."
    )

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

