# Runtime Control

Runtime Control defines how WAIL turns an evaluated execution state into an operational response.

WAIL currently supports three runtime decisions:

```text
OBSERVE
RETRY
REROUTE
```

A runtime decision and its execution are separate states.

When intervention is required, WAIL preserves the progression from the execution that produced the decision to the execution where recovery was applied and, where possible, verified.

---

# Control Lifecycle

The runtime control lifecycle is:

```text
Execution N
    │
    ▼
Runtime Assessment
    │
    ▼
Runtime Decision
    │
    ├──────────── OBSERVE
    │
    ├──────────── RETRY
    │
    └──────────── REROUTE
                       │
                       ▼
               Recovery Prepared
                       │
                       ▼
                 Execution N+1
                       │
                       ▼
                Recovery Applied
                       │
                       ▼
              Recovery Verification
```

Not every execution enters the recovery path.

`OBSERVE` requires no intervention.

`RETRY` and `REROUTE` can create recovery state that is subsequently applied to another execution.

---

# OBSERVE

`OBSERVE` preserves the current execution path.

Conceptually:

```text
Execution
    │
    ▼
OBSERVE
    │
    ▼
No Runtime Intervention
```

The execution and its runtime state are still recorded as evidence.

`OBSERVE` is therefore an explicit runtime decision, not the absence of runtime evaluation.

---

# RETRY

`RETRY` instructs WAIL to repeat execution against the applicable target.

Conceptually:

```text
Execution N
    │
    ▼
RETRY
    │
    ▼
Recovery Prepared
    │
    ▼
Execution N+1
Same Target
```

The retry decision belongs to the execution that produced it.

The resulting retry execution has its own execution identity and runtime state.

This allows WAIL to preserve the relationship between the source execution and the execution where the retry was applied.

---

# REROUTE

`REROUTE` instructs WAIL to use an alternate configured execution target.

For model execution, the alternate target can be another model or provider.

For supported MCP execution, the alternate target can be another configured tool route.

Conceptually:

```text
Execution N
Primary Target
    │
    ▼
REROUTE
    │
    ▼
Recovery Prepared
    │
    ▼
Execution N+1
Alternate Target
```

A reroute does not permanently change the model, provider, or tool configured by the application.

It applies to the relevant recovery execution.

---

# Execution Targets

Runtime control operates on targets already available to the application or configured for the applicable WAIL execution path.

For model execution, a target can identify:

```text
Provider
+
Model
```

For MCP recovery, a route can identify:

```text
Source Tool
    │
    ▼
Alternate Tool
```

Candidate evaluation can inform target selection.

The existence of an alternate target does not by itself cause a reroute.

A target becomes operationally relevant when the runtime decision selects an intervention and the corresponding recovery state is applied.

---

# Routing Stability

WAIL can evaluate whether changing execution targets is justified before producing or applying a reroute.

Routing stability prevents unnecessary movement between targets when an alternative does not provide sufficient reason for a route change.

This keeps target evaluation distinct from target execution:

```text
Candidate Exists
      ≠
Reroute Selected
      ≠
Reroute Applied
```

---

# Decision State

A runtime decision records the operational response selected from the evaluated execution state.

The decision belongs to the execution where that evaluation occurred.

For example:

```text
Execution N
    │
    └── decision = REROUTE
```

This does not establish that rerouting occurred.

It establishes only that WAIL selected `REROUTE` as the operational response.

---

# Recovery Preparation

When a control decision requires intervention, WAIL can prepare recovery state for subsequent execution.

Recovery preparation connects:

```text
Source Execution
        │
        ├── Decision
        │
        └── Intended Control Action
```

to the execution context where that action can later be applied.

Prepared recovery is not equivalent to applied recovery.

---

# Recovery Application

Recovery application records that a previously selected intervention was actually used.

Conceptually:

```text
Execution N
    │
    └── REROUTE
           │
           ▼
    Recovery Prepared
           │
           ▼
Execution N+1
    │
    └── Recovery Applied
```

The source and applied executions remain distinct.

This separation allows WAIL to distinguish:

```text
Decision Produced
        ≠
Decision Applied
```

and prevents a control decision from being reported as an executed intervention when no corresponding application occurred.

---

# N and N+1 Semantics

For recovery applied to a subsequent execution:

```text
N
│
├── runtime observations
├── assessment
└── RETRY / REROUTE decision
          │
          ▼
       recovery
          │
          ▼
N+1
│
├── recovery application
├── resulting target
├── runtime observations
└── execution outcome
```

`N` and `N+1` are separate executions.

Each can retain its own trace identity and runtime evidence.

The recovery relationship connects them without collapsing them into a single execution record.

---

# Recovery Verification

Applying recovery does not prove that recovery succeeded.

After an intervention has been applied, WAIL can evaluate the resulting execution and establish the recovery result.

```text
Decision
    │
    ▼
Application
    │
    ▼
Resulting Execution
    │
    ▼
Verification
```

This creates three separate control states:

```text
selected
applied
verified
```

They must not be treated as equivalent.

A recovery can therefore be:

```text
selected but not applied

applied but not yet verified

applied and verified
```

Where sufficient evidence is unavailable, verification remains explicitly unavailable rather than implying success.

---

# Recovery Outcome

Recovery verification is based on the resulting execution rather than the original decision.

Conceptually:

```text
Execution N
    │
    └── intervention selected
              │
              ▼
Execution N+1
    │
    ├── intervention applied
    ├── resulting execution observed
    └── recovery result evaluated
```

This prevents WAIL from treating the intent to recover as evidence that recovery occurred.

---

# Agent Run Recovery

When executions participate in an Agent Run, recovery state can also be associated with the larger run.

The individual executions retain their own trace identities:

```text
Agent Run
    │
    ├── Execution N
    │       └── recovery decision
    │
    └── Execution N+1
            ├── recovery application
            └── recovery verification
```

The Agent Run provides the execution context connecting these states.

It does not replace the underlying trace-level control evidence.

---

# MCP Runtime Control

MCP tool executions can participate in the same control semantics.

An MCP recovery route can map a primary tool to an alternate tool:

```text
Primary Tool
    │
    ▼
Runtime Decision
    │
    ▼
REROUTE
    │
    ▼
Alternate Tool
```

When the reroute is subsequently executed, WAIL records recovery application against the resulting MCP execution.

Where applicable, the resulting execution can then be used for recovery verification.

MCP transport and server execution remain part of the application's existing MCP infrastructure.

---

# Control State Invariants

Runtime Control maintains the following distinctions:

1. **Assessment is not a decision.**
2. **A candidate target is not a reroute.**
3. **A decision is not an application.**
4. **Prepared recovery is not applied recovery.**
5. **Applied recovery is not verified recovery.**
6. **Execution N and execution N+1 remain separate executions.**
7. **Reroute does not permanently modify application configuration.**
8. **Trace-level control state remains distinct from Agent Run recovery state.**

These distinctions prevent runtime-control intent from being represented as an execution outcome.

---

# Plan-Aware Control

Provider support and runtime control entitlement are separate.

An execution can be observed even when a particular intervention capability is unavailable.

Available runtime control capabilities depend on the active plan and license entitlements.

The evidence can therefore preserve a runtime decision even when the corresponding control action is not subsequently applied.

---

# Evidence

Runtime Control records control state into WAIL execution evidence.

The evidence model defines the semantic distinction between observation, assessment, decision, application, and verification.

Artifact formats define where those states are stored.

See:

- [Evidence Model](evidence-model.md)
- [Artifact Reference](artifact-reference.md)

---

# Summary

WAIL Runtime Control separates **what should happen** from **what actually happened**.

The control lifecycle is:

```text
Assessment
    ↓
Decision
    ↓
Preparation
    ↓
Application
    ↓
Verification
```

`OBSERVE` leaves execution unchanged.

`RETRY` repeats execution against the applicable target.

`REROUTE` moves the applicable recovery execution to an alternate configured target.

When recovery spans executions, the source execution and resulting execution remain independently identifiable while WAIL preserves the recovery relationship between them.

This allows WAIL to prove separately that an intervention was selected, applied, and evaluated.