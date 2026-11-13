from typing import Literal
from pydantic import BaseModel,model_validator

_RESULT_STATUS=Literal["passed", "failed", "error"]
_MAX_TEXT=500

def _clip(text:str|None) -> str|None:
    return text if text is None or len(text)<=_MAX_TEXT else text[:_MAX_TEXT]


class CaseResult(BaseModel):
    "One row in the test panel. Hidden rows can never carry details."
    label:str
    passed:bool
    visible:bool
    inputs:str | None = None
    expected:str | None = None
    got:str | None = None

    @model_validator(mode='after')
    def _hidden_shows_nothing(self):
        if not self.visible:
            self.inputs=self.expected=self.got=None
        else:
            self.inputs,self.expected,self.got=map(_clip,(self.inputs, self.expected, self.got))
        return self

class RunResult(BaseModel):
    "Response of /run and /submit."
    status:_RESULT_STATUS
    message:str | None = None
    cases:list[CaseResult]
    passed_count:int
    total:int

class SubmitResult(RunResult):
    attempt_no:int
    solved:bool
    give_up_available: bool