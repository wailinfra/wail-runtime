# Why WAIL

AI applications can receive a successful response from a model provider while the execution itself is operationally unhealthy.

A request can complete without an error while first-token latency increases several times over its normal baseline. Streaming can stall. Token delivery can become unstable. Total execution time can spike while the provider remains available and the API still returns successfully.

Monitoring can expose these conditions.

Application code can implement retries and rerouting.

Gateways can route traffic between providers.

But these capabilities do not, by themselves, provide a runtime layer that evaluates the health of the execution itself, determines what should happen because of that condition, applies control when justified, and preserves verifiable evidence of the result.

**WAIL exists to close that runtime gap.**

---

# Successful Does Not Mean Healthy

Traditional application logic often treats an AI request as successful when it returns without an error.

Runtime health requires a different view.

Suppose a model normally begins producing output within its established runtime range, but a request suddenly takes several times longer to produce its first token.

The provider is reachable.

The API call succeeds.

The model eventually returns a valid response.

Yet the execution has materially degraded.

Metrics, logs, and traces can expose that degradation, but identifying a runtime condition and determining what should happen because of it are different responsibilities.

A monitoring system can report increased latency, unstable streaming, retries, timeouts, or other runtime deviations.

It does not necessarily determine whether those conditions justify observation, retry, reroute, or no intervention at all.

WAIL connects observed runtime behavior to operational decisions using runtime evidence, historical behavior, execution state, policy, and available control capabilities.

**Observability tells you what happened. Runtime control determines what should happen next.**

---

# Resilience Should Not Live in Every Application

Applications can implement their own retries, timeouts, and rerouting logic.

At small scale, that may be enough.

As AI infrastructure expands across services, models, and providers, those decisions can become fragmented:

- one service retries after a timeout
- another reroutes after a latency threshold
- another contains provider-specific recovery logic
- another only records the failure
- each service produces different evidence about what occurred

Operational policy becomes distributed through application code.

WAIL separates runtime control from application business logic and provides a consistent control model around supported AI execution environments.

The application remains responsible for what it wants the model to do.

WAIL evaluates and controls the runtime behavior around that execution.

---

# WAIL Is Not a Gateway

WAIL does not require applications to replace their existing provider SDKs with a centralized AI gateway.

Instead, WAIL wraps existing provider clients.

```python
from openai import OpenAI
import wail

client = wail.wrap(OpenAI())
```

The application continues using its existing provider SDK and request flow.

Gateways solve valuable problems such as centralized routing, authentication, quotas, caching, provider abstraction, and traffic management.

WAIL solves a different problem:

**the operational state of AI execution itself.**

It can therefore complement existing gateways and infrastructure rather than requiring them to be replaced.

---

# From Execution to Decision

WAIL separates runtime control into distinct responsibilities:

```text
Observe
   │
   ▼
Assess
   │
   ▼
Decide
   │
   ▼
Control
   │
   ▼
Evidence
```

Observation establishes what happened during execution.

Assessment determines the operational state represented by those observations.

Decision determines the appropriate response according to runtime conditions and policy.

Control determines what is actually applied.

Evidence preserves the relationship between all of them.

Keeping these responsibilities separate matters.

**Detection is not intervention.**

A deviation can be detected without requiring execution to change.

An operational decision can be produced without the corresponding intervention being executed when the applicable control capability is unavailable.

When intervention does occur, WAIL preserves both the reason for the decision and the resulting execution outcome.

---

# Rerouting Does Not Change Application Configuration

Standard runtime reroute follows an N+1 model.

A degraded execution on request **N** can produce a runtime decision that changes the execution target for request **N+1** when intervention is justified and available.

The intervention does not permanently rewrite the provider or model configured by the application.

The application continues expressing its normal execution intent. WAIL applies runtime control when the current runtime state justifies it rather than permanently modifying application configuration.

This keeps runtime intervention separate from application intent.

---

# Stability Matters as Much as Rerouting

A different provider or model having a better candidate score does not automatically justify moving execution.

AI runtime behavior naturally fluctuates.

A control system that reacts to every small difference can create repeated route switching and introduce instability of its own.

WAIL therefore separates candidate evaluation from the decision to change the execution path.

Routing stability controls suppress unnecessary movement when the expected improvement does not justify a route change.

The objective is not to reroute as often as possible.

**The objective is to intervene when the runtime evidence justifies intervention.**

---

# Evidence, Not Just Logs

Once software begins making operational decisions automatically, knowing that an action occurred is not enough.

You also need to know why.

WAIL preserves the relationship between:

- observed runtime behavior
- runtime assessment
- operational decision
- execution target
- control state
- executed action
- execution outcome

A decision and an executed intervention are not treated as the same thing.

Generated runtime artifacts include cryptographic integrity information and signatures that allow the evidence to be independently verified.

The result is more than a log saying that a reroute happened.

It is signed evidence of the runtime conditions, decision, control state, and execution outcome associated with that intervention.

---

# On-Prem by Design

WAIL runs inside the customer's environment.

Runtime signals are processed locally as AI execution occurs.

Prompts, model responses, generated runtime evidence, and WAIL's local runtime state remain in the customer's environment and are not sent to a WAIL-hosted runtime data service.

WAIL may periodically transmit limited product-usage telemetry, such as an anonymous installation identifier, WAIL version, license plan, usage metrics, provider information, and model names. This telemetry does not include prompts, model responses, API credentials, runtime evidence, or customer application data.

Product telemetry is separate from WAIL's runtime control and evidence processing. Details are documented in [Telemetry](telemetry.md).

This allows organizations to add runtime control and verifiable evidence without introducing a WAIL-hosted data plane for their AI traffic.

The application's existing relationship with its chosen AI provider remains unchanged. WAIL operates around that execution inside the customer's environment.

---

# Deterministic Decisions

Runtime control should not produce arbitrary operational decisions from identical evidence.

WAIL's assessment and decision process is deterministic.

Given the same runtime evidence, execution state, policy, and control conditions, WAIL produces the same runtime assessment and operational decision.

Execution-specific measurements such as latency, timestamps, trace identifiers, hashes, and signatures naturally vary between separate requests.

Determinism applies to how WAIL evaluates the recorded runtime state and derives its operational decision.

This makes the relationship between evidence and decision reproducible and inspectable.

---

# One Runtime Model Across AI Environments

Production AI systems increasingly combine hosted model APIs, routing platforms, and self-hosted inference.

WAIL provides a consistent runtime model across:

- OpenAI
- Anthropic
- Google
- OpenRouter
- Ollama
- OpenAI-compatible runtimes 

These environments expose different APIs and execution characteristics, but the operational questions remain the same:

Was execution healthy?

Did runtime behavior materially deviate?

Was intervention justified?

What decision was made?

What actually happened?

What evidence remains afterward?

WAIL normalizes these questions into a consistent runtime control and evidence model instead of requiring every provider integration to become its own operational system.

OpenAI, Anthropic, and Google together account for an estimated 88% of enterprise LLM API usage in Menlo Ventures' 2025 U.S. enterprise research.

WAIL supports all three, plus routed and self-hosted environments including OpenRouter, Ollama, vLLM, and LM Studio.

Source: Menlo Ventures, *2025: The State of Generative AI in the Enterprise*.

---

# Governance Where Required

Runtime incidents can matter beyond immediate application performance.

Where enabled in Enterprise, WAIL can extend the same runtime evidence into governance, lifecycle, obligation, retention, and regulatory context.

This keeps governance connected to the execution evidence that produced it rather than reconstructing the event afterward.

---

# A Different Layer

WAIL does not try to replace the rest of the AI infrastructure stack.

It is not:

- an AI gateway
- a trace store
- an agent framework
- a workflow engine
- a model provider
- a provider SDK replacement
- a generic application performance monitoring platform

Those systems can continue doing their jobs.

A trace system can record an execution.

A monitoring system can surface degradation.

A gateway can move traffic.

Application code can implement recovery logic.

WAIL connects runtime observation, assessment, deterministic decision-making, intervention, and signed evidence as one runtime control model.

And it does so inside the customer's environment rather than requiring AI execution data to be transferred into a WAIL-hosted runtime service.

---

# Why WAIL

AI infrastructure already has tools for calling models, building applications, routing traffic, and monitoring systems.

The remaining problem is what happens **during and immediately after AI execution**:

Is this execution healthy?

Does the observed degradation justify intervention?

What should happen next?

Should the execution path actually change?

And can the resulting decision and action be independently verified afterward?

WAIL is built to answer those questions.

It provides a runtime control and governance layer that can:

- detect and assess meaningful runtime degradation
- produce deterministic decisions and apply runtime control when justified
- prevent unnecessary route churn while preserving application intent
- operate on-prem across major hosted, routed, and self-hosted AI environments
- preserve signed, independently verifiable runtime evidence under customer control

The application keeps its provider SDK and request flow.

The provider performs inference.

WAIL evaluates, controls, and records the runtime around that execution.

**That is the runtime gap WAIL is designed to fill.**