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

DEFAULT_MAX_CONTEXT = 8192
MIN_CONTEXT = 6144          
MAX_CONTEXT_LIMIT = 262_144
AUTO_MAX_CONTEXT = 16384

def _read_raw() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def _write_raw(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)

def load_max_context() -> int | None:
    "The learner's manual cap in tokens, or None for Auto."
    value = _read_raw().get("max_context")
    if isinstance(value, int) and MIN_CONTEXT <= value <= MAX_CONTEXT_LIMIT:
        return value
    return None

def forget_model(provider: str, model: str) -> None:
    "Remove a model from a provider's history. The active choice is not touched."
    _check(provider)
    data = _read_raw()
    history = data.get("models")
    if not isinstance(history, dict):
        return
    history[provider] = [m for m in (history.get(provider) or []) if m != model]
    data["models"] = history
    _write_raw(data)


def save_max_context(value: int | None) -> None:
    "A number sets a manual cap. None switches back to Auto."
    data = _read_raw()
    if value is None:
        data.pop("max_context", None)
    else:
        if not MIN_CONTEXT <= value <= MAX_CONTEXT_LIMIT:
            raise ValueError(
                f"Context must be between {MIN_CONTEXT} and {MAX_CONTEXT_LIMIT} tokens."
            )
        data["max_context"] = value
    _write_raw(data)

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
        data:dict=_read_raw()
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
    current=_read_raw()
    new=asdict(settings)
    merged={**current,**new}
    _write_raw(merged)

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