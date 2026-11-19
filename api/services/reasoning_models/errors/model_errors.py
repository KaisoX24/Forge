class ModelNotConfigured(Exception):
    "The learner hasn't chosen a provider and model yet."


class MissingApiKey(Exception):
    "An online provider is selected but no key is saved for it."

    def __init__(self, provider: str):
        super().__init__(f"No API key saved for {provider}")
        self.provider = provider