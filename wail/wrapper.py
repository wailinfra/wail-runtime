import time
from functools import wraps

from wail.core.fingerprint import compute_prompt_hash

from wail.runtime.context import (
    emit_event,
    get_ttft_watcher,
    mark_first_token,
    refresh_license_state,
    update_sampling_config,
    update_token_usage,
    wail_end,
    wail_retry,
    wail_start,
)
from wail.runtime.stream.unified_stream import UnifiedStream
from wail.runtime_config import _runtime_config
from wail_private import runtime_decision_store
from wail_private.client_inspector import inspect_client
from wail_private.client_registry import client_registry
from wail_private.control_executor import ControlExecutor
from wail_private.telemetry.client import trigger_telemetry
from wail_private.licensing.license import LicenseError
from wail_private.cli.errors import exit_license_error
from wail_private.licensing.runtime_entitlements import (
    authorize_runtime_registration,
    consume_control_authorization,
    model_allowed,
    model_allowed_after_control_quota,
    runtime_allowed,
)

def _runtime_request_allowed(runtime_id):

    license_state = refresh_license_state()
    return runtime_allowed(license_state, runtime_id)


def _model_request_allowed(provider, model):

    license_state = refresh_license_state()
    return model_allowed(license_state, provider, model)


def _control_request_allowed():
    state = refresh_license_state()
    result = consume_control_authorization(state)

    _runtime_config["_control_allowed"] = result.get("allowed", False)
    _runtime_config["_control_quota_reason"] = result.get("reason")

    return result.get("allowed", False)


def _quota_model_allowed(provider, model, control_allowed):
    state = refresh_license_state()
    return model_allowed_after_control_quota(
        state,
        provider,
        model,
        control_allowed,
    )


# =========================
# PROMPT EXTRACTION
# =========================

def _extract_prompt(args, kwargs):

    prompt_text = None

    # -----------------------------
    # CHAT MESSAGES 
    # -----------------------------
    if "messages" in kwargs and isinstance(kwargs["messages"], list):

        parts = []

        for m in kwargs["messages"]:

            if not isinstance(m, dict):
                continue

            role = m.get("role", "")
            content = m.get("content")

            if isinstance(content, str):
                parts.append(f"{role}:{content}")

            elif isinstance(content, list):

                for c in content:

                    if not isinstance(c, dict):
                        continue

                    text = c.get("text")

                    if text:
                        parts.append(f"{role}:{text}")

        if parts:
            prompt_text = " ".join(parts)

    # -----------------------------
    # RESPONSES API 
    # -----------------------------
    elif "input" in kwargs:

        inp = kwargs["input"]

        parts = []

        if isinstance(inp, str):
            parts.append(inp)

        elif isinstance(inp, list):

            for item in inp:

                if isinstance(item, str):
                    parts.append(item)

                elif isinstance(item, dict):

                    role = item.get("role", "")
                    content = item.get("content")

                    if isinstance(content, str):
                        parts.append(f"{role}:{content}")

                    elif isinstance(content, list):

                        for c in content:

                            if not isinstance(c, dict):
                                continue

                            text = c.get("text")

                            if text:
                                parts.append(f"{role}:{text}")

        if parts:
            prompt_text = " ".join(parts)

    # -----------------------------
    # LEGACY PROMPT
    # -----------------------------
    elif "prompt" in kwargs:

        if isinstance(kwargs["prompt"], str):
            prompt_text = kwargs["prompt"]

    # -----------------------------
    # POSITIONAL ARG FALLBACK
    # -----------------------------
    if not prompt_text and args:

        first_arg = args[0]

        if isinstance(first_arg, str):
            prompt_text = first_arg

        elif isinstance(first_arg, list):
            prompt_text = str(first_arg)

    return prompt_text

# =========================
# COMMON EXECUTION PIPELINE
# =========================
def execute_with_runtime(
    *,
    transport,
    provider,
    payload,
    client,
):
    control_allowed = _runtime_config.get("_control_allowed", True)

    if control_allowed:
        pending_decision = runtime_decision_store.consume()
    else:
        runtime_decision_store.consume()
        pending_decision = {
            "decision": "observe",
            "reason": "control_quota_exhausted",
        }

    executor = ControlExecutor()

    result = executor.execute(
        decision=pending_decision,
        original_kwargs=payload,
        current_provider=provider,
        current_transport=transport,
        client=client,
    )

    return {
        "response": result["response"],
        "provider": result["target"].provider,
        "model": result["target"].model,
        "transport": result["target"].transport,
        "execution_target": result["execution_target"],
    }

def wrap(
    client,
    *,
    transport=None,
):

    transport, provider = inspect_client(
        client,
        transport=transport,
    )

    # =========================
    # LICENSE CHECK
    # =========================

    result = refresh_license_state()

    if not result.get("valid"):
        exit_license_error(
            LicenseError("License is not valid.")
        )

    plan = result.get("plan")

    if not plan:
        exit_license_error(
            LicenseError("License plan is not available.")
        )

    runtime_id = id(client)
    runtime_auth = authorize_runtime_registration(
        result,
        runtime_id,
        provider,
    )

    if not runtime_auth.get("allowed"):
        limit = runtime_auth.get("limit")
        exit_license_error(
            LicenseError(
                f"Your current license supports only {limit} active runtime."
            )
        )

    if provider:
        client_registry.register(
            provider,
            client,
        )
    # =========================
    # OPENAI STREAMING PATH
    # =========================
    if hasattr(client, "responses") and hasattr(client.responses, "stream"):

        original_stream = client.responses.stream
        client.responses._original_stream = original_stream

        @wraps(original_stream)
        def wrapped_stream(*args, **kwargs):

            if not _runtime_request_allowed(runtime_id):
                return original_stream(*args, **kwargs)

            temperature = kwargs.get("temperature")
            top_p = kwargs.get("top_p")
            max_tokens = kwargs.get("max_output_tokens")

            prompt_text = _extract_prompt(args, kwargs)
            prompt_hash = compute_prompt_hash(prompt_text)

            mdl = kwargs.get("model")
            if not mdl and args:
                mdl = args[0]

            if not _model_request_allowed(provider, mdl):
                return original_stream(*args, **kwargs)

            control_allowed = _control_request_allowed()

            if not _quota_model_allowed(provider, mdl, control_allowed):
                return original_stream(*args, **kwargs)

            wail_start(
                model=mdl,
                provider=provider,
                transport=transport,
                sampling_params={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                },
                prompt_hash=prompt_hash,
            )
            update_sampling_config(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            payload = dict(kwargs)
            payload["stream"] = True

            try:

                result = execute_with_runtime(
                    transport=transport,
                    provider=provider,
                    payload=payload,
                    client=client,
                )

                return UnifiedStream(
                    manager=result["response"],
                    provider=result["provider"],
                    transport=result["transport"],
                    watcher=get_ttft_watcher(),
                    model=result["model"],
                )

            except Exception:
                wail_retry()
                raise

        client.responses.stream = wrapped_stream

        # =========================
        # OPENAI RESPONSES CREATE PATH
        # =========================
        if hasattr(client, "responses") and hasattr(client.responses, "create"):

            original_create = client.responses.create
            client.responses._original_create = original_create

            @wraps(original_create)
            def wrapped_create(*args, **kwargs):

                if not _runtime_request_allowed(runtime_id):
                    return original_create(*args, **kwargs)

                if kwargs.get("stream") is True: 
                    return original_create(*args, **kwargs)
                
                temperature = kwargs.get("temperature")
                top_p = kwargs.get("top_p")
                max_tokens = kwargs.get("max_output_tokens")

                prompt_text = _extract_prompt(args, kwargs)
                prompt_hash = compute_prompt_hash(prompt_text)

                mdl = kwargs.get("model")
                if not mdl and args:
                    mdl = args[0]

                if not _model_request_allowed(provider, mdl):
                    return original_create(*args, **kwargs)

                control_allowed = _control_request_allowed()

                if not _quota_model_allowed(provider, mdl, control_allowed):
                    return original_create(*args, **kwargs)

                wail_start(
                    model=mdl,
                    provider=provider,
                    transport=transport,
                    sampling_params={
                        "temperature": temperature,
                        "top_p": top_p,
                        "max_tokens": max_tokens,
                    },
                    prompt_hash=prompt_hash,
                )

                update_sampling_config(
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                )

                try:

                    result = execute_with_runtime(
                        transport=transport,
                        provider=provider,
                        payload=kwargs,
                        client=client,
                    )

                    response = result["response"]

                    if hasattr(response, "usage") and response.usage:
                        update_token_usage(
                            response.usage.input_tokens,
                            response.usage.output_tokens,
                        )

                    return response

                except Exception:
                    wail_retry()
                    raise

                finally:
                    wail_end()

            client.responses.create = wrapped_create

        return client

    # =========================
    # ANTHROPIC PATH
    # =========================
    if provider == "anthropic":

        original_create = client.messages.create

        client.messages._original_create = original_create

        @wraps(original_create)
        def wrapped_create(*args, **kwargs):

            if not _runtime_request_allowed(runtime_id):
                return original_create(*args, **kwargs)

            temperature = kwargs.get("temperature")
            top_p = kwargs.get("top_p")
            max_tokens = kwargs.get("max_tokens")

            prompt_text = _extract_prompt(args, kwargs)
            prompt_hash = compute_prompt_hash(prompt_text)

            mdl = kwargs.get("model")
            if not mdl and args:
                mdl = args[0]

            if not _model_request_allowed(provider, mdl):
                return original_create(*args, **kwargs)

            control_allowed = _control_request_allowed()

            if not _quota_model_allowed(provider, mdl, control_allowed):
                return original_create(*args, **kwargs)

            wail_start(
                model=mdl,
                provider=provider,
                transport=transport,
                sampling_params={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                },
                prompt_hash=prompt_hash,
            )

            update_sampling_config(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            # ================================
            # ARG NORMALIZATION
            # ================================

            if args:
                if "model" not in kwargs:
                    kwargs["model"] = args[0]

                if len(args) > 1 and "messages" not in kwargs:
                    kwargs["messages"] = args[1]

                args = ()

            try:

                result = execute_with_runtime(
                    transport=transport,
                    provider=provider,
                    payload=kwargs,
                    client=client,
                )

                response = result["response"]

                if hasattr(response, "usage"):

                    update_token_usage(
                        response.usage.input_tokens,
                        response.usage.output_tokens,
                    )

                return response

            except Exception:
                wail_retry()
                raise

            finally:
                wail_end()

        client.messages.create = wrapped_create
        original_stream = client.messages.stream

        client.messages._original_stream = original_stream


        @wraps(original_stream)
        def wrapped_stream(*args, **kwargs):

            if not _runtime_request_allowed(runtime_id):
                return original_stream(*args, **kwargs)

            temperature = kwargs.get("temperature")
            top_p = kwargs.get("top_p")
            max_tokens = kwargs.get("max_tokens")

            prompt_text = _extract_prompt(args, kwargs)
            prompt_hash = compute_prompt_hash(prompt_text)

            mdl = kwargs.get("model")
            if not mdl and args:
                mdl = args[0]

            if not _model_request_allowed(provider, mdl):
                return original_stream(*args, **kwargs)

            control_allowed = _control_request_allowed()

            if not _quota_model_allowed(provider, mdl, control_allowed):
                return original_stream(*args, **kwargs)

            wail_start(
                model=mdl,
                provider=provider,
                transport=transport,
                sampling_params={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                },
                prompt_hash=prompt_hash,
            )

            update_sampling_config(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            if args:
                if "model" not in kwargs:
                    kwargs["model"] = args[0]

                if len(args) > 1 and "messages" not in kwargs:
                    kwargs["messages"] = args[1]

                args = ()

            payload = dict(kwargs)
            payload["stream"] = True

            try:

                result = execute_with_runtime(
                    transport=transport,
                    provider=provider,
                    payload=payload,
                    client=client,
                )

                return UnifiedStream(
                    manager=result["response"],
                    provider=result["provider"],
                    watcher=get_ttft_watcher(),
                    model=result["model"],
                )

            except Exception:
                wail_retry()
                raise

        client.messages.stream = wrapped_stream
        return client

    # =========================
    # GOOGLE GENAI PATH
    # =========================
    if hasattr(client, "models"):

        # -----------------------------
        # NORMAL REQUEST
        # -----------------------------
        original_generate = client.models.generate_content
        client.models._wail_original_generate_content = original_generate

        @wraps(original_generate)
        def wrapped_generate(*args, **kwargs):

            if not _runtime_request_allowed(runtime_id):
                return original_generate(*args, **kwargs)
            
            temperature = kwargs.get("temperature")
            top_p = kwargs.get("top_p")
            max_tokens = kwargs.get("max_output_tokens")

            prompt_text = _extract_prompt(args, kwargs)
            prompt_hash = compute_prompt_hash(prompt_text)

            mdl = kwargs.get("model")
            if not mdl and args:
                mdl = args[0]


            if not _model_request_allowed(provider, mdl):
                return original_generate(*args, **kwargs)

            control_allowed = _control_request_allowed()

            if not _quota_model_allowed(provider, mdl, control_allowed):
                return original_generate(*args, **kwargs)

            wail_start(
                model=mdl,
                provider=provider,
                transport=transport,
                sampling_params={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                },
                prompt_hash=prompt_hash,
            )

            update_sampling_config(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            start_ts = time.perf_counter()

            emit_event(
                "stream_start",
                {
                    "t_offset_ms": 0,
                    "model": mdl,
                    "provider": provider,
                },
            )

            try:

                payload = dict(kwargs)

                if args:
                    payload.setdefault("contents", args[0])

                payload.setdefault("model", mdl)

                result = execute_with_runtime(
                    transport=transport,
                    provider=provider,
                    payload=payload,
                    client=client,
                )

                response = result["response"]

                first_token_offset = (time.perf_counter() - start_ts) * 1000

                mark_first_token()

                emit_event(
                    "first_token",
                    {
                        "t_offset_ms": round(first_token_offset, 2),
                    },
                )

                usage = getattr(response, "usage_metadata", None)

                if usage:
                    update_token_usage(
                        getattr(usage, "prompt_token_count", None),
                        getattr(usage, "candidates_token_count", None),
                    )

                emit_event(
                    "stream_end",
                    {
                        "t_offset_ms": round(
                            (time.perf_counter() - start_ts) * 1000,
                            2,
                        ),
                        "total_stream_chunks": 0,
                    },
                )

                return response

            except Exception:
                wail_retry()
                raise

            finally:
                wail_end()

        client.models.generate_content = wrapped_generate

        # -----------------------------
        # STREAMING
        # -----------------------------
        original_stream = client.models.generate_content_stream
        client.models._wail_original_generate_content_stream = original_stream

        @wraps(original_stream)
        def wrapped_stream(*args, **kwargs):

            if not _runtime_request_allowed(runtime_id):
                return original_stream(*args, **kwargs)

            temperature = kwargs.get("temperature")
            top_p = kwargs.get("top_p")
            max_tokens = kwargs.get("max_output_tokens")

            prompt_text = _extract_prompt(args, kwargs)
            prompt_hash = compute_prompt_hash(prompt_text)

            mdl = kwargs.get("model")
            if not mdl and args:
                mdl = args[0]

            if not _model_request_allowed(provider, mdl):
                return original_stream(*args, **kwargs)

            control_allowed = _control_request_allowed()

            if not _quota_model_allowed(provider, mdl, control_allowed):
                return original_stream(*args, **kwargs)

            wail_start(
                model=mdl,
                provider=provider,
                transport=transport,
                sampling_params={
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                },
                prompt_hash=prompt_hash,
            )

            update_sampling_config(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

            payload = dict(kwargs)

            if args:
                payload.setdefault("contents", args[0])

            payload.setdefault("model", mdl)
            payload["stream"] = True

            try:

                result = execute_with_runtime(
                    transport=transport,
                    provider=provider,
                    payload=payload,
                    client=client,
                )

                return UnifiedStream(
                    manager=result["response"],
                    provider=result["provider"],
                    watcher=get_ttft_watcher(),
                    model=result["model"],
                )

            except Exception:
                wail_retry()
                raise

        client.models.generate_content_stream = wrapped_stream

        return client


def safe_log_payload(payload):
    redacted = {}

    for k, v in payload.items():
        if k in ["messages", "input"]:
            redacted[k] = "<omitted>"
        elif isinstance(v, str) and len(v) > 200:
            redacted[k] = v[:200] + "...<truncated>"
        else:
            redacted[k] = v