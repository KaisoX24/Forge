import re
from dataclasses import dataclass

import ollama

@dataclass
class LocalModelInfo:
    max_context:int|None
    billions:float|None

def ollama_info(model:str) ->LocalModelInfo | None:
    "Ask the local Ollama server about a model. None if it isn't installed or Ollama is down."
    try:
        info = ollama.show(model)
    except Exception:
        return None

    max_context = None
    for key, value in (getattr(info, "modelinfo", None) or {}).items():
        if key.endswith(".context_length") and isinstance(value, int):
            max_context = value

    billions = None
    raw = getattr(getattr(info, "details", None), "parameter_size", None)  # "9.0B", "270M"
    if raw:
        m = re.match(r"([\d.]+)\s*([BM])", raw, re.I)
        if m:
            billions = float(m[1]) / (1000 if m[2].upper() == "M" else 1)

    return LocalModelInfo(max_context, billions)