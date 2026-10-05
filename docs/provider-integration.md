# Provider Integration

WAIL integrates with major hosted AI providers, routing platforms, local inference environments, and supported OpenAI-compatible runtimes.

WAIL wraps existing AI clients and applies a consistent runtime control and evidence model across supported providers.

---

# Supported Providers

WAIL currently supports the following providers and runtime interfaces.

| Provider | Runtime Detection | Runtime Control | Runtime Evidence |
|----------|:-----------------:|:---------------:|:----------------:|
| OpenAI | ✅ | ✅ | ✅ |
| Anthropic | ✅ | ✅ | ✅ |
| Google | ✅ | ✅ | ✅ |
| OpenRouter | ✅ | ✅ | ✅ |
| Ollama | ✅ | ✅ | ✅ |
| OpenAI-compatible Runtimes | ✅ | ✅ | ✅ |

Runtime control capabilities depend on the active plan and license entitlements.

---

# OpenAI

Wrap your existing OpenAI client:

```python
from openai import OpenAI
import wail

client = wail.wrap(OpenAI())
```

Continue using the wrapped client through the OpenAI SDK as usual.

---

# Anthropic

Wrap your existing Anthropic client:

```python
from anthropic import Anthropic
import wail

client = wail.wrap(Anthropic())
```

Continue using the wrapped client through the Anthropic SDK as usual.

---

# Google

Wrap your existing Google client:

```python
from google import genai
import wail

client = wail.wrap(genai.Client())
```

Continue using the wrapped client through the Google SDK as usual.

---

# OpenRouter

OpenRouter exposes an OpenAI-compatible API and can be used through an OpenAI client configured with the OpenRouter endpoint.

```python
from openai import OpenAI
import wail

client = wail.wrap(
    OpenAI(
        base_url="https://openrouter.ai/api/v1",
    )
)
```

Continue using the wrapped client through the OpenAI SDK as usual.

---

# Ollama

WAIL supports local Ollama inference through its OpenAI-compatible API.

```python
from openai import OpenAI
import wail

client = wail.wrap(
    OpenAI(
        base_url="http://localhost:11434/v1",
    )
)
```

---

# OpenAI-Compatible Runtimes

WAIL also works with supported inference servers that expose an OpenAI-compatible API.

Supported runtimes include:

- LM Studio
- vLLM

Configure the OpenAI client for the runtime endpoint, then wrap it with WAIL:

```python
from openai import OpenAI
import wail

client = wail.wrap(
    OpenAI(
        base_url="http://localhost:8000/v1",
    )
)
```

The integration pattern remains the same for supported OpenAI-compatible endpoints.

---

# Multi-Provider Applications

Applications can use WAIL across multiple supported provider clients without replacing their existing SDKs.

The integration pattern remains:

```python
client = wail.wrap(existing_client)
```

Each wrapped client retains its provider-specific execution path while WAIL normalizes the resulting runtime state into a consistent control and evidence model.

---

# Summary

WAIL provides a consistent integration pattern across supported hosted providers, routing platforms, local inference environments, and OpenAI-compatible runtimes.

Applications keep their existing provider SDKs and request flows while WAIL adds runtime detection, control, and evidence around those executions.