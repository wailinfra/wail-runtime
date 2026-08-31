from wail.providers import anthropic
from wail.providers import openai
from wail.providers import google
from wail.providers import ollama


class ProviderRegistry:

    _providers = {
        "anthropic": anthropic.MODELS,
        "openai": openai.MODELS,
        "google": google.MODELS,
        "ollama": ollama.MODELS,
    }

    @classmethod
    def register(cls, provider: str, models: list):

        cls._providers[provider] = list(models)

    @classmethod
    def get_models(cls, provider: str) -> list:

        return cls._providers.get(provider, [])

    @classmethod
    def has_provider(cls, provider: str) -> bool:

        return provider in cls._providers

    @classmethod
    def providers(cls) -> list:

        return list(cls._providers.keys())