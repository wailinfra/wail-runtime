# Why WAIL

AI systems can complete successfully while the execution itself is operationally unhealthy.

A model can respond while latency has materially degraded. Streaming can become unstable. A tool call can fail inside an otherwise valid agent run. Recovery can be attempted without establishing whether it actually worked.

Monitoring can expose symptoms.

Application code can implement recovery.

Gateways can route traffic.

Agent frameworks can orchestrate work.

But these capabilities do not, by themselves, provide a runtime layer responsible for evaluating execution state, deciding whether intervention is justified, applying control, verifying the result, and preserving evidence of what happened.

**WAIL exists to provide that runtime layer.**

---

# The Runtime Gap

Production AI is no longer a single request to a single model.

An execution can involve:

```text
Application
    │
    ├── Agent
    │     ├── Model
    │     ├── Tool
    │     └── Agent
    │
    └── Model
```

Each part can complete, degrade, fail, recover, or affect another part of the execution.

The application defines what the system is trying to accomplish.

The model provider performs inference.

Agent frameworks coordinate work.

MCP connects tools and services.

WAIL operates around those executions to determine their runtime state and preserve what occurred.

---

# Successful Does Not Mean Healthy

Traditional application logic often treats an AI operation as successful when it returns without an error.

Runtime health requires a different view.

A model request can return a valid response after materially abnormal latency.

A stream can complete after unstable delivery.

A tool can eventually return after degraded execution.

An agent run can complete while one of its underlying executions required recovery.

The final application result alone does not describe the operational history of the execution.

WAIL evaluates that runtime behavior independently of whether the application ultimately receives a successful result.

**Application success and runtime health are not the same thing.**

---

# Observability Is Necessary, but It Is Not Control

Metrics, logs, and traces can show what happened.

They can expose:

- latency changes
- streaming instability
- retries
- timeouts
- errors
- execution relationships

But observing a condition and determining what should happen because of it are different responsibilities.

WAIL connects runtime evidence to operational control.

That control can result in:

```text
OBSERVE
RETRY
REROUTE
```

Detection does not automatically imply intervention.

A runtime condition can be observed without changing execution.

An intervention can be selected without being applied.

An applied recovery can still require verification.

These distinctions are fundamental to WAIL's runtime model.

---

# Recovery Is More Than a Retry

Recovery is often represented as a single action:

```text
failure → retry
```

That loses important information.

WAIL separates:

```text
Decision
    │
    ▼
Recovery Preparation
    │
    ▼
Recovery Application
    │
    ▼
Resulting Execution
    │
    ▼
Recovery Verification
```

This means WAIL can distinguish between:

```text
recovery selected
recovery applied
recovery verified
```

A decision to recover is not evidence that recovery occurred.

Applying recovery is not evidence that recovery succeeded.

The resulting execution determines the recovery outcome.

See [Runtime Control](runtime-control.md) for the control semantics.

---

# Control Without Replacing Application Intent

WAIL does not require applications to move their execution logic into a new runtime platform.

Existing provider clients remain provider clients.

Existing agent orchestration remains application orchestration.

Existing MCP infrastructure remains MCP infrastructure.

WAIL instruments and controls the applicable execution path around them.

For model clients:

```python
from openai import OpenAI
import wail

client = wail.wrap(OpenAI())
```

The application continues using the provider SDK normally.

For agent systems, existing orchestration can execute inside a WAIL Agent Run.

For MCP, existing client sessions can be instrumented by WAIL.

The application still defines what should be executed.

WAIL determines the applicable runtime control around that execution.

---

# WAIL Is Not a Gateway

WAIL does not require AI traffic to be moved behind a centralized WAIL proxy.

Gateways solve valuable problems such as:

- centralized routing
- authentication
- quotas
- caching
- provider abstraction
- traffic management

WAIL solves a different problem:

**the operational state and control of AI execution itself.**

It can therefore operate alongside gateways rather than replacing them.

---

# Beyond Individual Model Requests

A trace can explain an individual model or tool execution.

Modern AI systems also need to understand how executions relate to one another.

WAIL Agent Runs provide a larger execution boundary containing relationships between:

```text
Agent Units
Model Units
MCP Tool Units
```

and execution relationships such as delegation and calls.

This allows runtime evidence to represent not only an isolated request but also the execution structure in which that request occurred.

Trace-level evidence remains independently identifiable.

Agent Run evidence connects those executions into a run-level record.

---

# Runtime Control Across Models and Tools

Runtime degradation is not limited to model providers.

A production execution may depend on a model call, an MCP tool call, another agent, or a combination of them.

WAIL applies a common runtime-control model across supported execution surfaces while preserving their individual execution identities.

For model execution, recovery can involve retrying or rerouting to another configured model or provider.

For supported MCP execution, recovery can involve an alternate configured tool route.

The control semantics remain consistent:

```text
observe
decide
apply
verify
```

The execution target changes; the distinction between decision and outcome does not.

---

# Evidence, Not Just Logs

Once software begins making operational decisions automatically, recording that an action occurred is not enough.

You also need to establish why it occurred and what happened afterward.

WAIL preserves evidence connecting runtime state with control state.

At the trace level, that can include the execution, assessment, decision, target, intervention, outcome, and cryptographic integrity information.

At the Agent Run level, WAIL can preserve the connected execution graph and run-level recovery state.

Generated evidence is cryptographically protected so its integrity can be verified independently.

The detailed semantics are defined in [Evidence Model](evidence-model.md).

Artifact structures are documented in [Artifact Reference](artifact-reference.md).

---

# Runtime Control Should Remain Separate From Business Logic

Applications can implement their own retries, timeouts, routing rules, and recovery behavior.

At small scale, that can be enough.

As AI systems expand across models, providers, agents, tools, and services, runtime-control logic can become fragmented across application code.

One service retries.

Another reroutes.

Another contains provider-specific recovery logic.

An agent handles tool failures differently.

Each produces different evidence about what happened.

WAIL provides a common runtime-control layer around supported AI executions while leaving application business logic in the application.

---

# On-Prem by Design

WAIL runs inside the customer's environment.

Runtime processing and generated execution evidence remain local rather than requiring AI traffic to pass through a WAIL-hosted runtime data plane.

The application's relationship with its model providers, MCP infrastructure, and other execution targets remains unchanged.

WAIL may transmit limited product-usage telemetry separately from runtime-control processing.

That telemetry does not include prompts, model responses, generated runtime evidence, API credentials, or customer application data.

See [Telemetry](telemetry.md) for the telemetry boundary.

---

# Governance From Execution Evidence

Operational evidence can also become governance evidence.

Where the applicable capabilities are enabled, WAIL can connect runtime execution evidence with governance, lifecycle, obligation, retention, and regulatory context.

This keeps governance tied to the execution that produced the evidence instead of reconstructing operational history afterward.

---

# A Different Layer

WAIL is not:

- an AI gateway
- an agent framework
- a workflow engine
- a model provider
- a provider SDK replacement
- a trace store
- a generic application performance monitoring platform

Those systems continue doing their jobs.

Providers perform inference.

Agent frameworks orchestrate work.

MCP connects tools.

Gateways manage traffic.

Observability systems expose operational data.

Applications define business behavior.

**WAIL provides runtime control and governance around the resulting AI execution.**

---

# Why WAIL

Production AI systems need more than the ability to execute.

They need to establish:

```text
What happened?

Was the execution operationally healthy?

Was intervention justified?

What control decision was made?

Was that decision actually applied?

What happened after intervention?

Did recovery succeed?

How did this execution relate to the rest of the agent run?

Can the resulting evidence be verified afterward?
```

WAIL is built to answer those questions.

It provides an **AI Runtime Control & Governance Layer** that operates around existing AI execution infrastructure.

The application keeps its execution logic.

Providers perform inference.

Agents keep their orchestration.

MCP keeps its tool infrastructure.

**WAIL evaluates, controls, verifies, and records the runtime around those executions.**