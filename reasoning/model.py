from langchain_ollama import ChatOllama
from functools import lru_cache

@lru_cache(maxsize=1)
def get_llm(model_card:str):
    return ChatOllama(model=model_card)