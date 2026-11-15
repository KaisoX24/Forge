from typing import Literal
from pydantic import BaseModel

class FilesRequest(BaseModel):
    files:dict[str,str]

class HintsResponse(BaseModel):
    hint_count:int
    hints:list[str]

class SolutionResponse(BaseModel):
    files:dict[str,str]

class StepStatus(BaseModel):
    status: Literal["open", "solved", "gave_up", "completed"]