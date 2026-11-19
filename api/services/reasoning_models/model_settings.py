import json
from dataclasses import asdict,dataclass,field
from pathlib import Path

import keyring
from keyring.errors import PasswordDeleteError

#Config path
APP_NAME="forge"
CONFIG_PATH=Path.home()/f'.{APP_NAME}'/'settings.json'

# LLm Providers
PROVIDERS = ("ollama", "openai", "anthropic", "google_genai")

@dataclass
class ModelSettings:
    provider:str
    model:str
    models:dict[str,list[str]]=field(default_factory=dict)

def _check(provider:str) ->None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown Provider: {provider}")



def load_settings() ->ModelSettings | None:
    "The saved choice, or None when the user hasn't chosen a model yet."
    try:
        data:dict=json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        provider,model=data.get("provider"),data.get('model')
        models=data.get("models",{})
        if provider not in PROVIDERS or not isinstance(model,str) or not model:
            return None
        if not isinstance(models,dict):
            models={}

        return ModelSettings(provider,model,models)

    except(OSError,ValueError,AttributeError):
        pass
    return None


def save_settings(provider:str,model:str) -> None:
    _check(provider)
    model=model.strip()
    if not model:
        raise ValueError("Model Name is Empty")

    current=load_settings()
    history=current.models if current else {}
    listed=[m for m in history.get(provider,[]) if m!=model]
    history[provider]=[model,*listed]

    settings=ModelSettings(provider,model,history)
    CONFIG_PATH.parent.mkdir(parents=True,exist_ok=True)
    tmp=CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings),indent=2),encoding='utf-8')
    tmp.replace(CONFIG_PATH)

def set_api_key(provider:str,key:str) -> None:
    _check(provider)
    keyring.set_password(APP_NAME,provider,key.strip())

def get_api_key(provider:str) ->str|None:
    _check(provider)
    return keyring.get_password(APP_NAME,provider)

def delete_api_key(provider:str)->None:
    _check(provider)
    try:
        keyring.delete_password(APP_NAME,provider)
    except PasswordDeleteError:
        pass