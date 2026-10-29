from typing import Any,Annotated,Literal,Union
from pydantic import BaseModel,Field,StringConstraints

Label=Literal['grounded', 'weak', 'unproved']
Short=Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=80)]

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


class ExerciseDraft(ExerciseSpec):
    # Draft for the Interactive Exercises
    function_name:str
    reference_solution:str
    tests:list[CaseDraft]=Field(min_length=3,max_length=6)
    hints:list[str]=Field(min_length=2,max_length=2)
    explanation:str=Field(max_length=500)


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


class Case(BaseModel):
    label:str
    inputs:list[Any]
    expected:Any
    visible:bool=True

class Exercise(ExerciseSpec):
    filename: str = "main.py"
    function_name: str
    starter_code: str
    cases: list[Case]
    hints: list[str]
    solution: str
    explanation: str

    @classmethod
    def from_draft(cls, draft: ExerciseDraft, *, starter_code: str, cases: list[Case]) -> "Exercise":
        shared = draft.model_dump(
            include=set(ExerciseSpec.model_fields) | {"function_name", "hints", "explanation"}
        )
        return cls(**shared, starter_code=starter_code, cases=cases, solution=draft.reference_solution)

class Lesson(BaseModel):
    schema_version:int=1
    id:str
    title:str
    summary:str
    you_will_learn:list[str]
    blocks:list[Block]
    docs:list[DocRef]
    exercise:Exercise|None=None