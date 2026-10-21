from langchain_ollama import ChatOllama
from langchain.chat_models import init_chat_model
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

@lru_cache(maxsize=1)
def get_online_llm(model_card:str):
    return init_chat_model(
        model=model_card,
        model_provider="openai",
        reasoning_effort="none",
    )

@lru_cache(maxsize=1)
def get_llm(model_card:str):
    return ChatOllama(model=model_card)