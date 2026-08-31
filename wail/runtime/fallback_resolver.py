def select_fallback_target(
    provider: str,
    current_model: str,
    registry: dict,
):

    candidates = []

    provider_models = []

    for key, stats in registry.items():

        try:
            p, model = key.split(":", 1)
        except ValueError:
            continue

        if p != provider:
            continue

        provider_models.append(model)

        if model == current_model:
            continue

        latency = stats.get("latency_p95", 9999)
        error = stats.get("error_rate", 1.0)

        score = (
            (1 / (latency + 1)) * 0.7
            + (1 - error) * 0.3
        )

        candidates.append(
            {
                "provider": provider,
                "model": model,
                "score": score,
                "latency": latency,
                "error": error,
            }
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    best = candidates[0]

    return best