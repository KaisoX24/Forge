from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from api.services.reasoning_models.model_settings import get_api_key,load_settings,ModelSettings
from api.services.reasoning_models.errors.model_errors import MissingApiKey,ModelNotConfigured
from reasoning.model import get_llm

def check_model_ready(rt:bool=False) ->ModelSettings | None:
    settings=load_settings()
    if settings is None:
        raise ModelNotConfigured("Choose a model in Settings first.")
    if settings.provider!='ollama' and not get_api_key(settings.provider):
        raise MissingApiKey(settings.provider)
    if rt:
        return settings


def get_model() -> BaseChatModel:
    "Build the model chosen in Settings. Called when a job starts, never at import time."
    settings=check_model_ready(rt=True)

    if settings.provider=='ollama':
        return get_llm(settings.model)
    
    key=get_api_key(settings.provider)

    return init_chat_model(
        model=settings.model,
        model_provider=settings.provider,
        api_key=key
    )