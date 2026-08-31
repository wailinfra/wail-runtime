from wail.runtime.context import set_ttft_watcher
from wail.runtime.watchers.first_token import FirstTokenWatcher
from wail.providers.executors.provider_executor_registry import EXECUTOR_MAP
from wail.providers.google import resolve_model_alias


def normalize_payload(
    source_transport,
    target_transport,
    payload,
):

    if source_transport == target_transport:

        if target_transport == "openai":
            return {
                **{
                    k: v
                    for k, v in payload.items()
                    if k not in ["messages", "max_tokens"]
                },
                "input": (
                    payload["messages"][0]["content"]
                    if isinstance(payload.get("messages"), list)
                    and payload["messages"]
                    else payload.get("input", "")
                ),
                "max_output_tokens": (
                    payload.get("max_output_tokens")
                    or payload.get("max_tokens")
                ),
                **(
                    {"stream": payload["stream"]}
                    if "stream" in payload else {}
                ),
            }

        return payload

    # ------------------------
    # OpenAI -> Anthropic
    # ------------------------
    if source_transport == "openai" and target_transport == "anthropic":

        result = {
            "model": payload["model"],
            "messages": [
                {
                    "role": "user",
                    "content": payload.get("input", ""),
                }
            ],
        }

        max_tokens = (
            payload.get("max_output_tokens")
            or payload.get("max_tokens")
        )

        result["max_tokens"] = (
            max_tokens
            if max_tokens is not None
            else 1024
        )

        if "temperature" in payload:
            result["temperature"] = payload["temperature"]

        if "top_p" in payload:
            result["top_p"] = payload["top_p"]

        if "stream" in payload:
            result["stream"] = payload["stream"]

        return result

    # ------------------------
    # Anthropic -> OpenAI
    # ------------------------
    if source_transport == "anthropic" and target_transport == "openai":

        return {
            "model": payload["model"],
            "input": (
                payload["messages"][0]["content"]
                if payload.get("messages")
                else ""
            ),
            "max_output_tokens": (
                payload.get("max_tokens")
                or payload.get("max_output_tokens")
            ),
            **(
                {"temperature": payload["temperature"]}
                if "temperature" in payload else {}
            ),
            **(
                {"top_p": payload["top_p"]}
                if "top_p" in payload else {}
            ),
            **(
                {"stream": payload["stream"]}
                if "stream" in payload else {}
            ),
        }

    return payload


def _execute_provider(
    source_transport,
    transport,
    provider,
    payload,
    client=None,
):

    ALLOWED_KEYS = {
        "model",
        "messages",
        "contents",
        "max_tokens",
        "input",
        "max_output_tokens",
        "temperature",
        "top_p",
        "stream",
    }

    clean_payload = {
        k: v
        for k, v in payload.items()
        if k in ALLOWED_KEYS
    }

    clean_payload = normalize_payload(
        source_transport=source_transport,
        target_transport=transport,
        payload=clean_payload,
    )

    if transport == "google":
        clean_payload["model"] = resolve_model_alias(
            clean_payload["model"]
        )

    stream = clean_payload.pop("stream", False)

    executor = EXECUTOR_MAP.get(transport)

    if not executor:
        raise Exception(
            f"No executor registered for transport '{transport}'"
        )

    mode = "stream" if stream else "sync"

    if stream:
        watcher = FirstTokenWatcher(threshold_ms=100)
        set_ttft_watcher(watcher)

    response = executor[mode](
        client,
        clean_payload,
    )

    return response, clean_payload




