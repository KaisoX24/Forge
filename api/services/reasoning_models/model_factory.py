import re
from dataclasses import dataclass

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from api.services.reasoning_models.model_settings import MIN_CONTEXT,load_max_context
from reasoning.model_limits import ollama_info
from api.services.reasoning_models.model_settings import get_api_key,load_settings,ModelSettings,AUTO_MAX_CONTEXT,DEFAULT_MAX_CONTEXT
from api.services.reasoning_models.errors.model_errors import MissingApiKey,ModelNotConfigured,ContextTooSmall
from reasoning.model import get_llm


@dataclass
class Limits:
    num_ctx: int
    num_predict: int = 2048

def resolve_limits() -> Limits:
    "The context window to use: the learner's cap, lowered to what a local model supports"
    settings = load_settings()
    if settings is None:
        raise ModelNotConfigured("Choose a model in Settings first.")

    manual=load_max_context()
    if settings.provider == "ollama":
        info = ollama_info(settings.model)
        supported=info.max_context if info and info.max_context else DEFAULT_MAX_CONTEXT
        num_ctx = min(manual or AUTO_MAX_CONTEXT,supported)

    else:
        num_ctx=manual or AUTO_MAX_CONTEXT

    if num_ctx < MIN_CONTEXT:
        raise ContextTooSmall(
            f"{settings.model} only supports a {num_ctx}-token context, "
            f"and generation needs at least {MIN_CONTEXT}. Pick a larger model."
        )
    return Limits(num_ctx)



def _provider_kwargs(provider: str, model: str) -> dict:
    if provider == "openai" and re.match(r"(gpt-5|o\d)", model):
        return {"reasoning_effort": "none"}
    return {}

def check_model_ready(rt:bool=False) ->ModelSettings | None:
    settings=load_settings()
    if settings is None:
        raise ModelNotConfigured("Choose a model in Settings first.")
    if settings.provider!='ollama' and not get_api_key(settings.provider):
        raise MissingApiKey(settings.provider)
    if rt:
        return settings


def get_model(limits:Limits) -> BaseChatModel:
    "Build the model chosen in Settings. Called when a job starts, never at import time."
    settings=check_model_ready(rt=True)

    if settings.provider=='ollama':
        return get_llm(settings.model,num_ctx=limits.num_ctx,num_predict=limits.num_predict)
    
    key=get_api_key(settings.provider)

    return init_chat_model(
        model=settings.model,
        model_provider=settings.provider,
        api_key=key,
        **_provider_kwargs(settings.provider, settings.model)
    )