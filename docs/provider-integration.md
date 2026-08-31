# Provider Integration

WAIL supports the AI stacks used by the vast majority of enterprise AI deployments: OpenAI, Anthropic, Google, OpenRouter, Ollama, and OpenAI-compatible runtimes including LM Studio and vLLM.

OpenAI, Anthropic, and Google alone accounted for an estimated 88% of enterprise LLM API usage in 2025.

WAIL wraps existing AI clients and applies a consistent runtime control model across supported providers.

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

Wrap your existing OpenAI client.

```python
from openai import OpenAI
import wail

client = wail.wrap(OpenAI())
```

Continue using the wrapped client through the OpenAI SDK as usual.

---

# Anthropic

Wrap your existing Anthropic client.

```python
from anthropic import Anthropic
import wail

client = wail.wrap(Anthropic())
```

Continue using the wrapped client through the Anthropic SDK as usual.

---

# Google

Wrap your existing Google client.

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

WAIL also works with inference servers that expose an OpenAI-compatible API.

Supported runtimes include:

- LM Studio
- vLLM

Configure the OpenAI client for the runtime endpoint, then wrap it with WAIL.

For example:

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

Applications can use WAIL across supported provider clients without replacing their existing provider SDKs.

The integration pattern remains the same:

```python
client = wail.wrap(existing_client)
```

WAIL normalizes supported provider executions into a consistent runtime control and evidence model.

---

# Enterprise Coverage

WAIL's direct provider support covers the three providers that together accounted for an estimated 88% of enterprise LLM API usage in 2025: Anthropic, OpenAI, and Google.

Support for OpenRouter, Ollama, and OpenAI-compatible runtimes extends that coverage to additional hosted, routed, and self-hosted AI deployments.

The 88% estimate is based on Menlo Ventures' 2025 U.S. enterprise research and represents estimated enterprise LLM API usage rather than a claim that WAIL covers exactly 88% of all AI deployments.

---

# Summary

WAIL provides a consistent integration layer across major hosted AI providers, model routing platforms, and OpenAI-compatible inference runtimes.

Applications keep their existing provider SDK and request flow while WAIL adds runtime monitoring, control, and evidence across supported AI environments.