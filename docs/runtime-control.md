# Runtime Control

Runtime Control is how WAIL observes and responds to AI execution as it happens.

As a request runs, WAIL evaluates runtime behavior, determines execution health, and decides whether an operational response is justified.

Runtime observations, decisions, control state, and execution outcomes are preserved as signed runtime evidence.

---

# Runtime Control Pipeline

WAIL processes supported AI requests through a consistent runtime control pipeline.

```text
Runtime Observation
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
```

Each stage contributes structured information to the runtime evidence generated for the execution.

---

# Runtime Observation

Runtime Control begins when an AI request starts.

During execution, WAIL observes signals such as:

- execution latency
- first-token latency
- streaming behavior
- retry activity
- timeout events
- execution errors
- workload characteristics

These signals describe the observed runtime state of the request.

---

# Runtime Assessment

Observed runtime signals are evaluated using historical baselines and runtime analysis.

The assessment can determine:

- execution health
- deviation severity
- dominant impact surface
- runtime confidence

At this stage, WAIL answers one question:

**What is happening right now?**

Runtime assessment describes the observed execution state without independently determining the operational response.

---

# Runtime Decision

After runtime assessment, WAIL determines the appropriate operational response according to runtime conditions, policy, and available control capabilities.

WAIL may decide to:

- observe
- retry
- reroute
- preserve runtime evidence

A runtime decision does not necessarily mean that an intervention will be executed. Execution depends on the active plan, available control capabilities, and applicable runtime policy.

Given the same runtime evidence, execution state, policy, and control conditions, WAIL produces the same runtime assessment and operational decision.

This stage answers the next question:

**What should happen next?**

The resulting decision becomes part of the runtime evidence.

---

# Execution Target

When an intervention is justified and available, WAIL determines the appropriate execution target.

Depending on the runtime decision, execution may:

- remain on the current provider and model
- retry an execution
- move to another model
- move to another provider

Candidate evaluation informs runtime control, but WAIL does not reroute requests simply because another execution target appears preferable.

Routing stability controls can prevent unnecessary movement between execution targets when the expected improvement does not justify a route change.

For standard runtime reroute, a decision produced from request **N** is applied to request **N+1**. The reroute does not permanently change the model or provider configured by the application.

---

# Runtime Action

Runtime Action represents what WAIL actually does after a runtime decision has been evaluated against the available control capabilities.

Possible outcomes include:

- continue execution
- execute a retry
- execute a reroute
- preserve runtime evidence without changing execution

A decision can therefore be recorded even when the active plan or runtime state does not permit the corresponding intervention.

The resulting control state and execution outcome become part of the runtime evidence.

---

# Runtime Evidence

Runtime Control preserves the information needed to understand the execution and WAIL's response.

Runtime evidence can include:

- observed runtime signals
- runtime assessment
- runtime decisions
- execution target
- control state
- executed actions
- execution outcome
- cryptographic integrity information

The evidence available depends on the active plan and execution outcome.

---

# Plan-Aware Control

Provider support and runtime control entitlement are separate.

A supported provider can be observed by WAIL even when a particular control capability is not available under the active plan.

Available runtime control capabilities depend on the active plan and license entitlements.

This allows the same runtime observation model to support different levels of operational control without changing the application's provider integration.

---

# Summary

Runtime Control transforms observed AI execution behavior into structured runtime assessment, deterministic operational decisions, and, where permitted, execution intervention.

By separating runtime observation, assessment, decision-making, execution targeting, and runtime action, WAIL provides a consistent runtime control model while preserving signed, verifiable evidence of what was observed, decided, and executed.