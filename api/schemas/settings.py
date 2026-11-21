from pydantic import BaseModel

class ActiveModel(BaseModel):
    provider:str
    model:str

class ProviderView(BaseModel):
    id:str
    label:str
    needs_key:bool
    has_key:bool
    models:list[str]

class SettingsView(BaseModel):
    active:ActiveModel|None
    providers:list[ProviderView]
    max_context:int | None
    auto_context:int
    min_context:int
    max_context_limit:int

class ModelChoice(ActiveModel):
    pass

class KeyBody(BaseModel):
    key:str

class ContextBody(BaseModel):
    max_context:int|None

class ModelInfoView(BaseModel):
    max_context:int|None
    billions:float|None=None



