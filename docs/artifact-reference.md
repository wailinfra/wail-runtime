# WAIL Runtime Artifact Reference

WAIL records AI execution as structured, signed runtime evidence.

Runtime artifacts provide a standardized representation of observed execution behavior, runtime assessment, operational decisions, control outcomes, and integrity information.

WAIL uses two artifact surfaces:

- technical runtime artifacts
- full runtime artifacts

The artifact surface available depends on the active plan and execution context.

---

# Artifact Types

## Technical Runtime Artifact

Developer and Pro generate technical runtime artifacts.

```text
trace_<TRACE_ID>_tech.json
```

Technical artifacts contain the runtime evidence needed to inspect execution behavior, assessment, decisions, control state, execution outcome, and cryptographic integrity.

They intentionally exclude the additional governance and compliance evidence available in the full artifact.

## Full Runtime Artifact

Enterprise can generate the full runtime artifact.

```text
trace_<TRACE_ID>.json
```

The full artifact extends runtime evidence with additional incident, governance, obligation, lifecycle, and compliance information where applicable.

---

# Artifact Structure

Runtime artifacts are composed of structured sections representing different parts of the execution and evidence lifecycle.

Depending on the artifact type and execution outcome, these can include:

- metadata
- execution
- execution_target
- content_proof
- runtime
- statistics
- drift_analysis
- risk
- decision_snapshot
- incident
- obligation
- escalation
- enforcement
- governance
- impact
- pre_incident
- control
- execution_flow
- recommended_action
- determinism
- integrity

Not every section is present in every artifact type or execution.

---

# Metadata

Metadata identifies the execution and its runtime context.

It can include information such as:

- trace_id
- timestamp
- provider
- model
- execution context

This information associates the artifact with the execution it represents.

---

# Execution

Execution information describes how the request was executed.

It can identify:

- initial execution path
- final execution path
- provider
- model
- whether execution changed
- execution outcome

This makes it possible to distinguish the requested execution path from the path that ultimately handled the request.

---

# Execution Target

When runtime control evaluates an alternative execution path, target information records the relevant execution relationship.

This can describe:

- source provider or model
- target provider or model
- execution transition

Execution target information provides context for control decisions without implying that every evaluated target was executed.

---

# Runtime

Runtime evidence captures behavior observed during execution.

Recorded information can include:

- execution duration
- first-token latency
- token counts
- streaming behavior
- retry activity
- timeout state
- execution errors
- other runtime measurements

These values describe the observed behavior of the request.

---

# Statistics

Statistical evidence provides the historical execution context used for runtime evaluation.

It can include:

- baseline measurements
- latency statistics
- first-token statistics
- sample information
- other historical runtime characteristics

These statistics provide the comparison context for current execution behavior.

---

# Drift Analysis

Drift analysis records deviations detected between current runtime behavior and historical execution behavior.

It can include:

- detected runtime signals
- baseline comparison
- runtime deviation
- impact information
- supporting measurements

This section provides evidence for why execution behavior was considered normal or abnormal.

---

# Risk

Risk information represents WAIL's structured assessment of the observed runtime condition.

It can include:

- severity
- risk surfaces
- dominant impact surface
- supporting runtime signals
- assessment results

Risk evidence describes the operational significance of the observed execution state.

---

# Runtime Decision

Runtime decisions record the operational response selected from the runtime assessment.

Decision-related evidence can include:

- decision snapshot
- control state
- execution target
- execution outcome

This allows the artifact to distinguish between what WAIL observed, what it decided, and what was actually executed.

---

# Incident

Where available, incident information records the operational classification associated with abnormal runtime behavior.

It can include:

- incident classification
- severity
- dominant impact surface
- trigger signals
- supporting evidence

Incident evidence provides structured context for significant runtime events.

---

# Obligation

Where governance and compliance capabilities are enabled, obligation information can associate runtime evidence with applicable requirements.

It can include:

- regulatory context
- reporting requirements
- retention requirements
- disclosure requirements
- other applicable obligations

This information connects runtime evidence with governance requirements where applicable.

---

# Escalation

Escalation information records whether runtime conditions resulted in an elevated operational state.

It can include:

- escalation status
- incident context
- resulting control state
- supporting evidence

---

# Governance

Where governance capabilities are enabled, governance information can record the lifecycle associated with an incident.

It can include:

- incident identity
- governance state
- lifecycle information
- applicable deadlines

This provides governance context alongside the underlying runtime evidence.

---

# Determinism

Determinism information contains fingerprints and identifiers derived from execution evidence.

It can include:

- request fingerprint
- trace fingerprint
- prompt hash

These values support consistent identification and verification of recorded execution state.

`prompt_hash` is derived from the prompt for execution evidence. WAIL does not persist the raw prompt as part of runtime evidence.

The deterministic behavior of WAIL's assessment and decision process is described in the Runtime Evidence Model.

---

# Integrity

Integrity information protects generated runtime evidence against undetected modification.

It can include:

- artifact hash
- state hash
- signature
- public key fingerprint
- integrity metadata

WAIL uses cryptographic signatures to make generated runtime evidence independently verifiable.

---

# Verification

Both technical and full runtime artifacts can be verified using the WAIL CLI.

```bash
wail verify <ARTIFACT_FILE>
```

Verification confirms:

- artifact integrity
- signature validity
- deterministic artifact structure

For artifact verification examples, see [Getting Started](getting-started.md).