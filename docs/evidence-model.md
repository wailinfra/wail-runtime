# WAIL Evidence Model

WAIL represents observed AI execution as structured and verifiable evidence.

The evidence model preserves the distinction between what was observed, how it was assessed, what was decided, what was applied, and what execution state was ultimately established.

WAIL evidence exists at two connected scopes:

```text
Trace Evidence
      │
      │ referenced by
      ▼
Agent Run Evidence
```

Trace evidence represents an individual model or MCP execution.

Agent Run evidence represents the connected execution containing multiple execution units and their relationships.

---

# Evidence Semantics

WAIL evidence follows a state-explicit model.

```text
Observed
   │
   ▼
Assessed
   │
   ▼
Decided
   │
   ▼
Applied
   │
   ▼
Verified
```

These states are not interchangeable.

An observation does not imply an assessment.

An assessment does not imply an intervention.

A decision does not prove that the selected action was applied.

An applied recovery does not prove that recovery succeeded.

Verification records the resulting state only when sufficient evidence exists to establish it.

This distinction is fundamental to the WAIL evidence model.

---

# Trace Evidence

Trace evidence represents one observed runtime execution.

Each trace has its own execution identity and preserves the evidence associated with that execution.

The evidence can represent:

- observed runtime behavior
- runtime assessment
- operational decision
- control state
- execution path
- execution outcome
- deterministic identifiers
- integrity state

The trace remains independently meaningful even when it participates in a larger Agent Run.

---

# Observed Evidence

Observed evidence is information obtained from execution itself.

Examples include execution timing, streaming behavior, errors, timeouts, retry activity, and other runtime measurements.

Observed evidence forms the factual basis for later evaluation.

WAIL keeps observation separate from interpretation so that recorded execution behavior can be distinguished from conclusions derived from it.

---

# Assessment Evidence

Assessment evidence represents WAIL's evaluation of observed execution state.

It can describe concepts such as:

- execution health
- severity
- dominant impact surface
- supporting runtime signals
- evaluation state

Assessment evidence remains separate from the operational decision.

This allows the evidence supporting a decision to be inspected independently of the action selected in response.

---

# Decision Evidence

Decision evidence records the operational response selected from the available execution state.

A decision represents what WAIL determined should happen.

It does not, by itself, establish that the action occurred.

Conceptually:

```text
Decision
   │
   ├── OBSERVE
   │
   ├── RETRY
   │
   └── REROUTE
```

The detailed conditions and runtime semantics of these decisions are defined in [Runtime Control](runtime-control.md).

---

# Application Evidence

When an intervention is selected, application evidence records whether the selected control action was subsequently applied.

This creates an explicit distinction:

```text
Decision Produced
        ≠
Recovery Applied
```

For recovery that affects a subsequent execution, the evidence can connect the source execution that produced the decision with the execution where the recovery action was applied.

The absence of application evidence must not be interpreted as successful recovery.

---

# Verification Evidence

Verification evidence represents the evaluated result of an applied recovery.

The evidence model therefore distinguishes:

```text
Recovery Selected
        │
        ▼
Recovery Applied
        │
        ▼
Recovery Verified
```

A verified result requires evidence from the resulting execution.

If verification cannot be performed, the evidence state remains explicitly unavailable or not applicable rather than implying success or failure.

---

# Execution Evidence

Execution evidence preserves the execution path and resulting outcome.

It distinguishes between concepts such as:

```text
requested execution
effective execution
execution transition
execution outcome
```

This allows WAIL to preserve the difference between what the application requested and what ultimately executed.

---

# Agent Run Evidence

Agent Run evidence represents execution at a scope above an individual trace.

It binds related execution units and relationships into a single run-level evidence record.

```text
Agent Run
   │
   ├── Agent Unit
   │
   ├── Model Unit ───── Trace Evidence
   │
   ├── MCP Tool Unit ── Trace Evidence
   │
   └── Relations
```

The Agent Run does not replace the underlying trace evidence.

Instead, it preserves information that cannot be represented by an isolated trace alone: which executions belonged to the same run and how those executions were related.

---

# Evidence Relationships

Agent Run evidence preserves relationships between execution units.

A relationship is evidence about execution structure.

For example:

```text
Agent A ── delegates ──> Agent B

Agent B ── calls ──────> Model Unit

Agent B ── calls ──────> MCP Tool Unit
```

These relationships allow the evidence record to preserve execution structure without copying the complete contents of every underlying trace into the Agent Run artifact.

---

# Run-Level Evidence

Some execution state can only be evaluated with context from the larger run.

Run-level evidence can therefore represent state associated with areas such as:

- execution pathology
- causal attribution
- execution localization
- execution propagation
- runtime recovery
- recovery verification

Run-level conclusions remain distinct from trace-level observations.

A conclusion at one level must not silently overwrite or reinterpret evidence at the other level.

---

# Evidence Availability

Not every evidence component is available for every execution.

WAIL preserves this explicitly.

Depending on context, an evidence component can be:

```text
evaluated
not_evaluated
not_applicable
```

An unavailable conclusion is not equivalent to a negative conclusion.

For example:

```text
not_evaluated
```

does not mean:

```text
no problem detected
```

and:

```text
not_applicable
```

does not mean:

```text
recovery failed
```

This prevents absence of evidence from being represented as evidence of absence.

---

# Evidence Linking

Trace and Agent Run evidence are connected through execution identity.

Conceptually:

```text
RUN_ID
  │
  └── Model / MCP Unit
            │
            └── TRACE_ID
```

`TRACE_ID` identifies the individual runtime execution.

`RUN_ID` identifies the connected Agent Run.

This relationship allows detailed runtime evidence to remain independently addressable while preserving its run-level context.

---

# Determinism

Determinism applies to WAIL's evaluation and decision process.

Given the same relevant runtime evidence, execution state, policy, and control conditions, WAIL produces the same assessment and operational decision.

Execution-specific observations are not expected to be identical across separate executions.

Values such as:

- measured latency
- timestamps
- execution identifiers
- hashes
- signatures

describe a particular execution and can naturally differ between requests.

Deterministic evaluation therefore does not require identical runtime observations.

---

# Standardization

WAIL normalizes supported execution surfaces into a consistent evidence model.

Provider-specific and execution-specific details can differ while preserving the same semantic separation between:

```text
Observation
Assessment
Decision
Application
Verification
Outcome
Integrity
```

Agent Run evidence extends this model with execution relationships and run-level state without changing the meaning of the underlying trace evidence.

---

# Integrity

Integrity evidence binds a generated evidence record to its recorded state.

Cryptographic protection allows later modification of signed evidence to be detected.

Integrity applies to the evidence record itself; it does not convert an unavailable or unevaluated runtime conclusion into an established one.

Artifact-specific integrity fields and verification mechanisms are documented in [Artifact Reference](artifact-reference.md).

---

# Evidence and Governance

Execution evidence is the factual input to governance capabilities where those capabilities are enabled.

```text
Execution Evidence
        │
        ▼
Governance Context
```

Governance can associate additional lifecycle, obligation, regulatory, or compliance context with execution evidence.

It does not alter the underlying observed execution record.

---

# Core Evidence Invariants

The WAIL evidence model maintains the following invariants:

1. **Observation is distinct from assessment.**
2. **Assessment is distinct from decision.**
3. **Decision is distinct from application.**
4. **Application is distinct from verification.**
5. **Unavailable evidence is not interpreted as a negative result.**
6. **Trace evidence remains distinct from Agent Run evidence.**
7. **Run-level conclusions do not replace underlying trace evidence.**
8. **Execution relationships are preserved explicitly.**
9. **Signed evidence protects recorded state without changing its semantics.**

---

# Summary

WAIL evidence preserves execution state without collapsing distinct stages into a single result.

At the individual execution level, Trace Evidence records runtime observation, assessment, decision, control, and outcome.

At the connected execution level, Agent Run Evidence records execution units, relationships, run-level state, and links to the underlying traces.

Across both levels, WAIL preserves a common principle:

```text
what was observed
        ≠
what was assessed
        ≠
what was decided
        ≠
what was applied
        ≠
what was verified
```

This separation allows WAIL execution evidence to remain explicit, inspectable, and independently verifiable.