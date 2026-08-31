MODELS = [
    {"id": "gemini-pro-latest"},
    {"id": "gemini-2.5-flash"},
    {"id": "gemini-2.5-flash-lite"},
]

GOOGLE_MODEL_ALIASES = {
    "gemini-2.5-pro": "gemini-pro-latest",
}

def resolve_model_alias(model: str) -> str:
    return GOOGLE_MODEL_ALIASES.get(model, model)