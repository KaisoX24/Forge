from fastapi import APIRouter

from api.errors.errors import Invalid
from api.schemas.settings import ActiveModel,ModelChoice,ProviderView,SettingsView,KeyBody
from api.services.reasoning_models.model_settings import(
    PROVIDERS,get_api_key,load_settings,save_settings,set_api_key,delete_api_key
)
from api.services.reasoning_models.errors.model_errors import MissingApiKey

router=APIRouter(tags=['settings'])
Labels={
    "ollama": "Ollama (local)",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google_genai": "Gemini",
}

def _view() ->SettingsView:
    active=load_settings()
    history=active.models if active else {}
    return SettingsView(
        active=ActiveModel(provider=active.provider,model=active.model) if active else None,
        providers=[
            ProviderView(
                id=p,
                label=Labels.get(p),
                needs_key=p!='ollama',
                has_key=p=='ollama'or bool(get_api_key(p)),
                models=history.get(p,[]),
            )
            for p in PROVIDERS
        ]
    )

def _online(provider: str) -> None:
    if provider not in PROVIDERS:
        raise Invalid("Unknown provider.")
    if provider == "ollama":
        raise Invalid("Ollama runs locally and needs no API key.")

@router.get("/api/settings",response_model=SettingsView)
def read_settings() ->SettingsView:
    return _view()

@router.put("/api/settings/model",response_model=SettingsView)
def choose_model(body:ModelChoice):
    "Make this the active model. Online providers need a saved key first."
    if body.provider not in PROVIDERS:
        raise Invalid("Unknown provider.")
    if not body.model.strip():
        raise Invalid("Enter a model name.")

    if body.provider!='ollama' and not get_api_key(body.provider):
        raise MissingApiKey(body.provider)

    save_settings(body.provider,body.model)
    return _view()

@router.put("/api/settings/keys/{provider}",response_model=SettingsView)
def save_key(provider:str,body:KeyBody):
    "Save/Replace a key, Saved goes to the system credential manager."
    _online(provider)
    key=body.key.strip()
    if not key:
        raise Invalid("Paste your API key first.")
    if len(key)>500:
        raise Invalid("That doesn't look like an API key.")
    set_api_key(provider, key)
    return _view()

@router.delete("/api/settings/keys/{provider}", response_model=SettingsView)
def remove_key(provider: str):
    _online(provider)
    delete_api_key(provider)
    return _view()