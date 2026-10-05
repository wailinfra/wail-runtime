# Getting Started

Get WAIL running in a few minutes.

Start with your existing AI client and request flow. WAIL wraps the client and adds runtime observation, control, and signed execution evidence without replacing the provider SDK.

---

# Prerequisites

Before you begin, make sure you have:

- Python 3.12
- An API key for one of the supported AI providers

---

# Install

Install WAIL using pip:

```bash
pip install wail-runtime
```

---

# Wrap Your AI Client

Create your provider client normally and wrap it with WAIL:

```python
from openai import OpenAI
import wail

client = wail.wrap(OpenAI())
```

Continue using the wrapped client through the provider SDK as usual.

---

# Make Your First Request

```python
response = client.responses.create(
    model="gpt-4o-mini",
    input="Explain AI in one sentence.",
)

print(response.output_text)
```

WAIL observes the execution and produces the applicable runtime state and evidence.

---

# Runtime Summary

After a measured execution, WAIL prints a runtime summary containing the execution identity and applicable runtime state.

The information displayed can vary according to execution type, execution outcome, and active capabilities.

---

# Agent Runs

Existing agent orchestration can execute inside a WAIL Agent Run:

```python
import wail

with wail.execution_run(
    attributes={
        "orchestration": "coordinator_worker",
    }
) as run:
    run_id = run.run_id

    # Existing agent orchestration continues here.
```

WAIL does not replace the agent framework or orchestration logic.

The Agent Run provides the execution boundary used to connect related agent, model, and MCP tool activity into run-level evidence.

For complete working examples, see:

```text
examples/multi_agent_mcp_evidence.py
examples/multi_agent_runtime_recovery_evidence.py
```

---

# MCP Tool Execution

WAIL can instrument an existing MCP client session:

```python
from wail.mcp.adapter import wrap_mcp

wrapped_session = wrap_mcp(
    session,
    transport="stdio",
    service="mcp",
    env="production",
)
```

Continue making MCP calls through the wrapped session.

When MCP execution occurs inside an Agent Run, the resulting tool execution can participate in the run-level execution evidence.

For complete MCP client and server setup, see:

```text
examples/multi_agent_mcp_evidence.py
examples/multi_agent_mcp_server.py
```

---

# MCP Recovery Routes

Where runtime recovery is enabled, an MCP wrapper can define an alternate tool route:

```python
wrapped_session = wrap_mcp(
    session,
    transport="stdio",
    service="mcp",
    env="production",
    routes={
        "primary_tool": "backup_tool",
    },
)
```

This makes the alternate tool available to WAIL's runtime recovery path when a reroute decision is produced.

For a complete recovery example, see:

```text
examples/multi_agent_runtime_recovery_evidence.py
```

---

# Inspect Runtime Artifacts

List runtime incidents:

```bash
wail traces incidents
```

Inspect a specific runtime trace:

```bash
wail trace show <TRACE_ID>
```

Inspect the underlying trace data where available:

```bash
wail trace show <TRACE_ID> --raw
```

Artifact structure is documented in [Artifact Reference](artifact-reference.md).

---

# Verify Runtime Artifact Integrity

Verify a signed runtime artifact:

```bash
wail verify <ARTIFACT_FILE>
```

Developer and Pro technical runtime artifacts use:

```text
wail_audit/trace_<TRACE_ID>_tech.json
```

Enterprise full runtime artifacts use:

```text
wail_audit/trace_<TRACE_ID>.json
```

For Agent Run evidence, use the verification path demonstrated by the public Agent/MCP examples.

The artifact formats and integrity fields are documented in [Artifact Reference](artifact-reference.md).

---

# Next Steps

- [Architecture](architecture.md) — execution architecture and boundaries
- [Runtime Control](runtime-control.md) — runtime decisions, intervention, and recovery
- [Evidence Model](evidence-model.md) — evidence semantics
- [Artifact Reference](artifact-reference.md) — artifact structures and fields
- [Provider Integration](provider-integration.md) — provider-specific integration
- [CLI Reference](CLI.md) — command-line operations