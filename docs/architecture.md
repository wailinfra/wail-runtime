# WAIL Architecture

WAIL is an AI Runtime Control & Governance Layer for production AI systems.

During AI execution, WAIL observes runtime behavior, evaluates execution health, applies runtime control when necessary and permitted by the active plan, and generates signed runtime evidence.

Instead of replacing your provider SDK or request flow, WAIL wraps your existing AI client and observes execution from request to completion.

---

# System Overview

WAIL processes supported AI requests through a consistent runtime pipeline.

As execution progresses, WAIL captures runtime signals, evaluates execution health, determines whether intervention is justified, and records the resulting execution state as signed runtime evidence.

The same runtime control model is applied across supported AI providers.

---

# Runtime Execution Pipeline

A WAIL-managed AI invocation follows the core runtime pipeline:

```text
AI Invocation
        │
        ▼
Runtime Signal Capture
        │
        ▼
Baseline Comparison
        │
        ▼
Drift Detection
        │
        ▼
Runtime Assessment
        │
        ▼
Runtime Decision
        │
        ▼
Execution Target
        │
        ▼
Runtime Action
        │
        ▼
Runtime Evidence
        │
        ▼
Cryptographic Verification
```

Where enabled by the active plan, runtime evidence can also feed incident classification, governance, and compliance capabilities.

---

# Runtime Signal Capture

Execution begins with runtime observation.

WAIL captures signals such as:

- execution latency
- first-token latency
- streaming behavior
- token throughput
- retry activity
- execution errors
- timeout events

These observations provide the runtime evidence used by later evaluation and control stages.

---

# Baseline Comparison & Drift Detection

Observed runtime behavior is compared with historical execution baselines.

This stage can identify unusual runtime behavior by analyzing:

- latency changes
- duration spikes
- workload shifts
- streaming anomalies
- statistical deviation

If execution behaves within expected conditions, WAIL continues observing the current execution path. When abnormal behavior is detected, the observed deviation becomes part of the runtime assessment.

---

# Runtime Assessment

Observed runtime signals are evaluated to determine the operational state of the execution.

The assessment can determine:

- execution health
- severity
- dominant impact surface
- runtime confidence

This stage describes **what happened** without independently determining **what should happen next**.

---

# Runtime Decision

Based on the runtime assessment, WAIL determines the appropriate operational response.

Runtime Decision translates observed runtime conditions into an operational decision according to the active runtime policy and available plan capabilities.

Depending on runtime conditions, policy, and entitlement, WAIL may:

- continue execution
- retry execution
- reroute execution
- preserve runtime evidence

Separating runtime assessment from runtime decision allows control policy to determine the appropriate response without changing the underlying runtime observations.

---

# Execution Target & Runtime Action

When intervention is justified and available under the active plan, WAIL determines how execution should continue.

Depending on the runtime decision, execution may:

- continue on the current execution path
- retry the request
- reroute to another model or provider

Runtime reroute applies to the next request and does not permanently change the model or provider configured by the application.

The resulting control state and execution outcome become part of the runtime evidence.

---

# Incident Classification

Where enabled by the active plan, abnormal executions can be classified into a structured incident model.

Classification can incorporate:

- runtime severity
- deviation magnitude
- dominant impact surface
- supporting runtime evidence

Incident information can then be used by additional governance capabilities where available.

---

# Governance

Where enabled by the active plan, WAIL extends runtime control and evidence with governance and compliance capabilities.

Governance capabilities can associate runtime incidents and execution evidence with structured information such as:

- incident lifecycle
- governance state
- retention requirements
- applicable obligations
- regulatory context

These capabilities build on the same runtime observations and execution evidence used by the core runtime control layer.

---

# Runtime Evidence

WAIL assembles observed runtime information, assessment results, decisions, control state, execution outcomes, and integrity information into signed runtime evidence.

The evidence available depends on the active plan and execution outcome.

---

# Cryptographic Verification

Runtime evidence includes cryptographic integrity information and can be independently verified.

Cryptographic verification provides a way to confirm that generated evidence has not been modified after generation.

---

# Architectural Principles

WAIL is built around four core principles.

## Runtime First

Runtime evaluation is based on observed execution behavior.

## Deterministic

Runtime assessment and operational decisions are deterministic for the same runtime evidence, execution state, policy, and control conditions.

## Provider Agnostic

The runtime control and evidence model remains consistent across supported AI providers.

## Verifiable

Runtime evidence is cryptographically verifiable.

---

# Summary

WAIL combines runtime observation, assessment, deterministic decision-making, execution control, evidence generation, and optional governance capabilities in a consistent architecture across supported AI providers.