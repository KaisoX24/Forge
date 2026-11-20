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

class ModelChoice(ActiveModel):
    pass

class KeyBody(BaseModel):
    key:str

