from langchain_ollama import ChatOllama
from langchain.chat_models import init_chat_model
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

@lru_cache(maxsize=1)
def get_online_llm(model_card:str):
    "Instance for Online Frontier Models"
    return init_chat_model(
        model=model_card,
        model_provider="openai",
        reasoning_effort="none",
    )

@lru_cache(maxsize=8)
def get_llm(model_card: str,*,num_ctx: int = 8192,temperature: float = 0.2,num_predict: int = 2048,reasoning: bool | None = False) -> ChatOllama:
    "Instance for Local Models"
    return ChatOllama(
        model=model_card,
        temperature=temperature,
        num_ctx=num_ctx,
        num_predict=num_predict,
        reasoning=reasoning
    )