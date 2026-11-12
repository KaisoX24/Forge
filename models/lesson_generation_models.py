from typing import Any,Annotated,Literal,Union
from pydantic import BaseModel,Field,StringConstraints,model_validator,field_validator
from enum import Enum
from pathlib import PurePosixPath

Label=Literal['grounded', 'weak', 'unproved']
Short=Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=80)]

class ExecutionTarget(str,Enum):
    FUNCTION='function'
    HTTP='http'

class FunctionExecutionConfig(BaseModel):
    target: Literal["function"]
    entry_file: str = "main.py"
    function_name: str

class HttpExecutionConfig(BaseModel):
    target: Literal["http"]
    command: list[str] = Field(
        description="Command used to start the application, e.g. python main.py"
    )
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    readiness_path: str = "/"

ExecutionConfig = Annotated[
    Union[FunctionExecutionConfig, HttpExecutionConfig],
    Field(discriminator="target"),
]

class FunctionCaseDraft(BaseModel):
    label:Short
    inputs:list[Any]

class HttpCaseDraft(BaseModel):
    label: Short
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    json_body: Any | None = None
    expected_status: int = Field(ge=100, le=599)
    expected_json: Any | None = None
    expected_text: str | None = None

    @field_validator("expected_text")
    @classmethod
    def blank_means_unchecked(cls, value: str | None) -> str | None:
        return None if value is not None and not value.strip() else value

class FunctionEvaluationConfig(BaseModel):
    target:Literal['function']
    cases:list[FunctionCaseDraft]=Field(min_length=3,max_length=6)

class HttpEvaluationConfig(BaseModel):
    target: Literal["http"]
    cases: list[HttpCaseDraft] = Field(min_length=3, max_length=6)

EvaluationConfig = Annotated[
    Union[FunctionEvaluationConfig, HttpEvaluationConfig],
    Field(discriminator="target"),
]

class KeyPoint(BaseModel):
    # Keypoints for the current Lesson
    title:Short
    text:str=Field(max_length=140)

class LessonDraft(BaseModel):
    # Draft for the Lesson"
    summary:str=Field(max_length=160)
    you_will_learn:list[Short]=Field(min_length=3,max_length=4)
    concept_heading:Short
    concept_text:str=Field(max_length=600)
    key_points:list[KeyPoint]=Field(min_length=2,max_length=3)
    example_title:Short
    example_language: Literal["python", "bash", "text"] = Field(
        default="python",
        description="python for code, bash for shell commands, text for config files or other output",
    )
    example_code:str=Field(max_length=900)
    tip:str=Field(max_length=200)

class CaseDraft(BaseModel):
    #Draft for test cases          
    label: Short                    
    inputs: list[Any]

class ExerciseSpec(BaseModel):
    title:Short
    description:str=Field(max_length=200)
    instructions:list[Short]=Field(min_length=2,max_length=4)
    difficulty:Literal['easy','medium','hard']


def _validate_project_files(files: dict[str, str]) -> dict[str, str]:
    if not files:
        raise ValueError("A project must contain at least one file.")

    for filename in files:
        path = PurePosixPath(filename)

        if (
            not filename
            or "\\" in filename
            or path.is_absolute()
            or ".." in path.parts
            or filename.endswith("/")
        ):
            raise ValueError(f"Invalid project file path: {filename!r}")

    return files

class ExerciseDraft(ExerciseSpec):
    # Draft for the Interactive Exercises
    files:dict[str,str] = Field(
        description="Files provided to the learner as the starter project."
    )
    reference_files:dict[str,str] = Field(
        description="Complete reference implementation, retained internally."
    )

    execution:ExecutionConfig
    evaluation:EvaluationConfig

    hints:list[str]=Field(min_length=2,max_length=2)
    explanation:str=Field(max_length=500)

    @field_validator("files", "reference_files")
    @classmethod
    def validate_files(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_project_files(value)

    @model_validator(mode='after')
    def validate_target_consistency(self):
        if self.execution.target != self.evaluation.target:
            raise ValueError(
                "Execution and evaluation targets must match."
            )
        if isinstance(self.execution, FunctionExecutionConfig):
            if self.execution.entry_file not in self.files:
                raise ValueError(
                    "The function entry file must exist in the starter project."
                )
            if self.execution.entry_file not in self.reference_files:
                raise ValueError(
                    "The function entry file must exist in the reference project."
                )

        if isinstance(self.execution, HttpExecutionConfig):
            if not self.execution.command:
                raise ValueError("HTTP execution requires a launch command.")

        return self

class ReferenceDraft(ExerciseSpec):
    reference_files: dict[str,str] = Field(
        description="Complete reference implementation, retained internally.",
    )
    execution: ExecutionConfig

    @field_validator('reference_files')
    @classmethod
    def validate_reference_files(cls,value:dict[str,str]) -> dict[str,str]:
        return _validate_project_files(value)

class StarterDraft(BaseModel):
    files: dict[str, str] = Field(
        description="Files provided to the learner as the starter project."
    )
    hints: list[str] = Field(min_length=2, max_length=2)

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_project_files(value)

class CasesDraft(BaseModel):
    evaluation:EvaluationConfig
    explanation: str = Field(max_length=500)

class FunctionCase(FunctionCaseDraft):
    expected: Any
    visible: bool = True

class HttpCase(HttpCaseDraft):
    visible: bool = True



# Blocks
class TextBlock(BaseModel):
    type:Literal['text']='text'
    heading:str|None=None
    body:str

class KeyPointsBlock(BaseModel):
    type: Literal["key_points"]="key_points"
    items: list[KeyPoint]

class CodeBlock(BaseModel):
    type:Literal['code']='code'
    title:str
    language:str='python'
    code:str
    output:str|None=None

class CalloutBlock(BaseModel):
    type: Literal["callout"] = "callout"
    kind: Literal["tip", "warning", "note"] = "tip"
    text: str

Block = Annotated[Union[TextBlock, KeyPointsBlock, CodeBlock, CalloutBlock], Field(discriminator="type")]


class DocRef(BaseModel):
    label:str
    url:str
    grounding:Label
    coverage:float=Field(ge=0,le=1)


class Case(CaseDraft):
    expected:Any
    visible:bool=True

class Exercise(ExerciseSpec):
    files: dict[str, str]
    execution: ExecutionConfig
    cases: list[FunctionCase | HttpCase]
    hints: list[str]
    explanation: str

    reference_files: dict[str,str]=Field(default_factory=dict)

    @classmethod
    def from_draft(
        cls,
        draft: ExerciseDraft,
        *,
        cases: list[FunctionCase | HttpCase],
    ) -> "Exercise":
        return cls(
            **draft.model_dump(
                exclude={"evaluation"}
            ),
            cases=cases,
        )

class Lesson(BaseModel):
    schema_version:int=1
    id:str
    title:str
    summary:str
    you_will_learn:list[str]
    blocks:list[Block]
    docs:list[DocRef]
    exercise:Exercise|None=None