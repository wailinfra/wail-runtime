# Getting Started

Get WAIL running in just a few minutes.

You'll wrap your existing AI client, make a normal request, and automatically receive runtime monitoring, signed runtime evidence, and a runtime summary.

---

# Prerequisites

Before you begin, make sure you have:

- Python 3.12
- An API key for one of the supported AI providers

---

# Install

Install WAIL using pip.

```bash
pip install wail-runtime
```

---

# Create a Client

Wrap your existing AI client with WAIL.

```python
from openai import OpenAI
import wail

client = wail.wrap(OpenAI())
```

Continue using the wrapped client through the provider SDK as usual.

---

# Make Your First Request

Use your wrapped client exactly as you normally would.

```python
response = client.responses.create(
    model="gpt-4o-mini",
    input="Explain AI in one sentence."
)

print(response.output_text)
```

WAIL observes the request without requiring you to replace your existing provider SDK or request flow.

---

# Runtime Summary

After each measured request, WAIL prints a runtime summary showing the observed execution, runtime assessment, and applicable control state.

The information available in the summary may vary depending on the active plan and the execution outcome.

---

# Inspect Runtime Artifacts

WAIL generates signed runtime evidence according to the capabilities of the active plan.

List runtime incidents:

```bash
wail traces incidents
```

Inspect a specific runtime trace:

```bash
wail trace show <TRACE_ID>
```

For lower-level inspection, the CLI can also expose the underlying trace data where available:

```bash
wail trace show <TRACE_ID> --raw
```

---

# Verify Artifact Integrity

WAIL runtime artifacts include cryptographic integrity information and can be verified using the CLI.

Verify an artifact:

```bash
wail verify <ARTIFACT_FILE>
```

Developer and Pro plans generate technical runtime artifacts:

```bash
wail verify wail_audit/trace_<TRACE_ID>_tech.json
```

Enterprise generates the full runtime artifact:

```bash
wail verify wail_audit/trace_<TRACE_ID>.json
```

Successful verification confirms:

- artifact integrity
- signature validity
- deterministic artifact structure

---

# Plan Capabilities

Available runtime control, evidence, governance, retention, and other capabilities depend on the active WAIL plan and license entitlements.

Provider support indicates that WAIL can integrate with that provider. It does not imply that every runtime control or governance capability is enabled on every plan.

---

# Next Steps

Learn more about how WAIL works.

- [Architecture](architecture.md)
- [Runtime Control](runtime-control.md)
- [Runtime Evidence Model](evidence-model.md)
- [Runtime Artifact Reference](artifact-reference.md)
- [Provider Integration](provider-integration.md)
- [CLI Reference](CLI.md)