from pydantic import BaseModel,Field,field_validator,StringConstraints
from enum import Enum
import re
from typing import Annotated
import json
import hashlib


_TITLE_PREFIX = re.compile(r"^\s*(module|lesson|unit)\s*\d+\s*[:.\-\u2013]\s*", re.I)


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REQ = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([A-Za-z0-9._,\s-]+)\])?$")
_VERSION = re.compile(r"^[0-9][A-Za-z0-9.!+_-]*$")
_APT = re.compile(r"^[a-z0-9][a-z0-9.+-]*$")


def _norm(name:str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

def canonical_requirement(raw: str) -> str:
    m = _REQ.fullmatch(raw.strip())
    if not m:
        raise ValueError(f"bad package name: {raw!r}")
    extras = sorted({_norm(e.strip()) for e in (m.group(2) or "").split(",") if e.strip()})
    name = _norm(m.group(1))
    return f"{name}[{','.join(extras)}]" if extras else name

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

class DocScan(BaseModel):
    imports:dict[str,list[str]]
    install_hints:dict[str,list[str]]

class EnvironmentSpec(BaseModel):
    python:str="3.11"
    packages:dict[str,str]=Field(default_factory=dict)
    apt:list[str]=[]
    memory_mb:int=Field(default=256,ge=64,le=2048)

    @field_validator('python')
    @classmethod
    def _python(cls,v:str) -> str:
        if not re.fullmatch(r"3\.\d{1,2}", v):
            raise ValueError("python must look like '3.11'")
        return v

    @field_validator('packages')
    @classmethod
    def _packages(cls, v: dict[str, str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for raw, version in v.items():
            if not _VERSION.fullmatch(version):
                raise ValueError(f"version for {raw} must be an exact pin like '1.2.3', got {version!r}")
            key = canonical_requirement(raw)
            if out.get(key, version) != version:
                raise ValueError(f"conflicting pins for {key}: {out[key]} vs {version}")
            out[key] = version
        return dict(sorted(out.items()))

    @field_validator('apt')
    @classmethod
    def _apt(cls, v: list[str]) -> list[str]:
        for pkg in v:
            if not _APT.fullmatch(pkg):
                raise ValueError(f"bad apt package: {pkg!r}")
        return sorted(set(v))

    @property
    def env_id(self) ->str:
        "Courses with identical spec share one image."
        canonical = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]

    @property
    def image_tag(self) -> str:
        return f"forge-sbx:{self.env_id}"


class RetrievedDocument(BaseModel):
    content:str
    metadata:dict
    distance:float

