# WAIL Artifact Reference

WAIL records execution state as structured, signed evidence.

This reference describes the artifact surfaces produced by WAIL and the information represented by each artifact type.

---

# Artifact Types

WAIL has three evidence surfaces:

| Artifact | Scope | File |
|---|---|---|
| Technical Runtime Artifact | Individual model or MCP execution | `trace_<TRACE_ID>_tech.json` |
| Full Runtime Artifact | Individual execution with extended governance evidence | `trace_<TRACE_ID>.json` |
| Agent Run Evidence | Connected agent execution graph | `agent_run_<RUN_ID>.json` |

Artifact availability depends on the active plan and execution context.

---

## Technical Runtime Artifact

Developer and Pro generate technical runtime artifacts.

```text
trace_<TRACE_ID>_tech.json
```

A technical runtime artifact represents one observed execution.

It can contain:

- execution identity
- runtime measurements
- baseline and statistical context
- detected runtime signals
- runtime assessment
- runtime decision
- control state
- execution target
- execution outcome
- deterministic identifiers
- cryptographic integrity information

Technical artifacts intentionally exclude the additional governance and compliance evidence available in the full runtime artifact.

---

## Full Runtime Artifact

Enterprise can generate the full runtime artifact.

```text
trace_<TRACE_ID>.json
```

The full runtime artifact extends individual execution evidence with additional governance and compliance information where applicable.

This can include:

- incident information
- obligations
- escalation state
- enforcement state
- governance lifecycle
- impact information
- additional compliance evidence

The full artifact remains associated with a single `TRACE_ID`.

---

## Agent Run Evidence

Agent Run evidence represents a connected agent execution.

```text
agent_run_<RUN_ID>.json
```

Unlike trace artifacts, which represent individual model or MCP executions, Agent Run evidence records the larger execution graph containing those executions.

An Agent Run artifact can contain:

- Run ID
- run status
- run attributes
- Agent Units
- Model Units
- MCP Tool Units
- execution relationships
- underlying Trace IDs
- baseline state
- run-level intelligence
- runtime recovery state
- recovery verification state
- integrity information

A Model Unit or MCP Tool Unit can reference its underlying runtime `TRACE_ID`, linking run-level evidence to individual runtime evidence.

---

# Runtime Artifact Structure

Technical and full runtime artifacts use structured sections representing different parts of an individual execution.

Depending on artifact type and execution outcome, sections can include:

```text
metadata
execution
execution_target
content_proof
runtime
statistics
drift_analysis
risk
decision_snapshot
incident
obligation
escalation
enforcement
governance
impact
pre_incident
control
execution_flow
recommended_action
determinism
integrity
```

Not every section is present in every artifact.

---

## Metadata

`metadata` identifies the execution and its runtime context.

Typical information includes:

```text
trace_id
timestamp
provider
model
execution context
```

---

## Execution

`execution` records the execution path and resulting execution state.

It can identify:

```text
initial execution path
final execution path
provider
model
execution changed
execution outcome
```

This allows the artifact to distinguish the requested execution path from the path that ultimately handled the request.

---

## Execution Target

`execution_target` records the relevant source and target execution paths when runtime control evaluates or applies an alternative.

It can include:

```text
source provider
source model
target provider
target model
execution transition
```

The presence of a target does not by itself imply that the target was executed.

---

## Runtime

`runtime` contains measurements observed during execution.

Depending on execution type, these can include:

```text
duration
first-token latency
token counts
streaming measurements
retry activity
timeout state
execution errors
tool execution measurements
```

Unavailable measurements can remain absent or null according to the artifact schema.

For example, token-stream measurements are not inherently applicable to MCP tool execution.

---

## Statistics

`statistics` contains historical execution context used during runtime evaluation.

This can include:

```text
baseline measurements
latency statistics
first-token statistics
sample information
historical runtime characteristics
```

Baseline state can also indicate that sufficient observations have not yet been collected.

---

## Drift Analysis

`drift_analysis` records runtime signals and deviations established from the current execution and its comparison context.

It can include:

```text
runtime signals
baseline comparison
runtime deviation
impact information
supporting measurements
```

---

## Risk

`risk` represents the structured runtime assessment associated with the execution.

It can include:

```text
severity
risk surfaces
dominant impact surface
supporting signals
assessment results
```

---

## Decision Snapshot

`decision_snapshot` preserves the runtime decision state associated with the execution.

It can contain information used to distinguish:

```text
observed runtime state
selected runtime decision
decision reason
control availability
baseline state at decision time
```

The exact decision and control semantics are documented in [Runtime Control](runtime-control.md).

---

## Control

`control` records runtime-control state associated with the execution.

Depending on the execution, this can distinguish states such as:

```text
no intervention
control prepared
control executed
```

This section should not be interpreted independently of the execution and decision state.

---

## Incident

Where available, `incident` records structured incident information associated with abnormal runtime behavior.

It can include:

```text
incident classification
severity
dominant impact surface
trigger signals
supporting evidence
```

---

## Obligation

Where governance capabilities are available, `obligation` can associate runtime evidence with applicable requirements.

It can include:

```text
regulatory context
reporting requirements
retention requirements
disclosure requirements
applicable obligations
```

---

## Escalation

`escalation` can record whether an execution entered an elevated operational state.

It can include:

```text
escalation status
incident context
resulting control state
supporting evidence
```

---

## Governance

Where governance capabilities are available, `governance` records governance state associated with the runtime evidence.

It can include:

```text
incident identity
governance state
lifecycle information
applicable deadlines
```

---

## Determinism

`determinism` contains identifiers and fingerprints derived from execution evidence.

It can include:

```text
request_fingerprint
trace_fingerprint
prompt_hash
```

`prompt_hash` is derived from the prompt used for execution evidence.

WAIL does not persist the raw prompt as part of runtime evidence.

---

## Integrity

`integrity` contains cryptographic integrity information for the generated artifact.

Depending on the artifact, this can include:

```text
artifact hash
state hash
signature
public key fingerprint
signature algorithm
integrity metadata
```

Signed WAIL evidence uses SHA-256 hashing and RSA-PSS-SHA256 signatures where applicable.

---

# Agent Run Artifact Structure

Agent Run evidence uses a separate run-level structure.

Its purpose is to preserve the connected execution rather than duplicate every field from the underlying runtime traces.

---

## Run Identity

The artifact identifies the Agent Run using its `run_id`.

Run-level state can also include:

```text
status
sequence
attributes
baseline state
```

The run identity is separate from the `trace_id` values associated with individual model and MCP executions.

---

## Units

The run contains execution units.

Current unit types include:

```text
Agent Unit
Model Unit
MCP Tool Unit
```

Each unit preserves its identity and execution state within the run.

Model and MCP Tool Units can reference their underlying runtime trace.

Conceptually:

```text
Agent Run
    │
    ├── Agent Unit
    │       │
    │       ├── Model Unit
    │       │       └── trace_id
    │       │
    │       └── MCP Tool Unit
    │               └── trace_id
    │
    └── ...
```

---

## Relations

Relations describe execution relationships between units.

Current relationship kinds include:

```text
calls
delegates
joins
```

A relation identifies the participating execution units and the relationship between them.

Relations preserve execution structure without requiring the Agent Run artifact to duplicate the underlying trace artifacts.

---

## Run-Level Intelligence

Agent Run evidence can contain run-level intelligence state for:

```text
execution pathology
causal attribution
execution localization
execution propagation
runtime recovery
recovery verification
```

These fields preserve explicit state.

When prerequisites are unavailable, a component can remain:

```text
not_evaluated
```

or:

```text
not_applicable
```

rather than implying that an evaluation occurred.

---

## Recovery State

Where runtime recovery occurs, Agent Run evidence can preserve the relationship between the execution that produced the recovery decision and the execution where recovery was applied.

Recovery evidence can distinguish:

```text
source execution
recovery decision
recovery application
applied execution
recovery verification
```

Detailed recovery semantics are documented in [Runtime Control](runtime-control.md).

---

## Agent Run Integrity

Agent Run evidence contains its own cryptographic integrity information.

Observed Agent Run evidence includes:

```text
evidence hash
public key fingerprint
signature
signature algorithm
```

Signed Agent Run evidence uses:

```text
RSA-PSS-SHA256
```

The Agent Run signature protects the run-level evidence record independently of the individual runtime traces referenced by the run.

---

# Relationship Between Artifacts

Trace and Agent Run artifacts represent different evidence scopes.

```text
agent_run_<RUN_ID>.json
        │
        ├── Agent Unit
        │
        ├── Model Unit
        │       └── trace_id
        │              │
        │              └── trace_<TRACE_ID>_tech.json
        │
        └── MCP Tool Unit
                └── trace_id
                       │
                       └── trace_<TRACE_ID>_tech.json
```

The Agent Run artifact preserves the execution graph.

The referenced trace artifacts preserve the detailed runtime state of individual model and MCP executions.

One does not replace the other.

---

# Verification

Technical and full runtime artifacts can be verified using the WAIL CLI:

```bash
wail verify <ARTIFACT_FILE>
```

Verification can validate artifact integrity, signature validity, and expected artifact structure.

Agent Run evidence is also cryptographically signed and can be verified through the Agent Run evidence verification path demonstrated by the public Agent/MCP examples.

For complete working Agent Run examples, see:

- `examples/multi_agent_mcp_evidence.py`
- `examples/multi_agent_runtime_recovery_evidence.py`

For installation and basic runtime artifact verification, see [Getting Started](getting-started.md).