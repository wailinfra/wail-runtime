# WAIL Runtime Evidence Model

Every AI execution observed by WAIL produces runtime evidence.

The Runtime Evidence Model defines how observed execution behavior, runtime assessment, decisions, control state, and execution outcomes are represented as structured and verifiable evidence.

Rather than relying only on raw execution logs, WAIL records meaningful runtime information and preserves the relationship between what was observed, what was assessed, what was decided, and what was executed.

---

# Evidence Composition

Runtime evidence represents the execution across several related dimensions:

- runtime observations
- runtime assessment
- operational decisions
- control state
- execution outcome
- execution fingerprints
- cryptographic integrity information

Together, these elements provide a structured record of the execution and WAIL's response to it.

---

# Observed Evidence

Runtime evidence begins with behavior observed during execution.

This can include:

- execution timing
- first-token latency
- streaming behavior
- retry activity
- execution errors
- timeout events
- other runtime signals

These observations establish the factual runtime basis of the evidence record.

WAIL distinguishes observed execution behavior from later assessment and decision information so that the evidence preserves both what occurred and how that behavior was interpreted.

---

# Assessment Evidence

Runtime assessment records WAIL's evaluation of the observed execution state.

Assessment evidence can describe:

- execution health
- deviation severity
- dominant impact surface
- supporting runtime signals
- other evaluation results

Assessment remains distinct from the operational decision that follows it.

This distinction makes it possible to inspect the evidence supporting a decision independently of the action ultimately taken.

---

# Decision and Control Evidence

Runtime evidence records both the operational decision and the resulting control state.

These are separate concepts.

A decision records what WAIL determined should happen based on the available runtime evidence and policy.

Control evidence records how that decision affected execution, including cases where execution continued without intervention.

This distinction allows the evidence record to show:

- what WAIL observed
- how the execution was assessed
- what WAIL decided
- whether execution was changed
- the resulting execution outcome

A recorded decision therefore does not, by itself, imply that the corresponding intervention was executed.

---

# Execution Evidence

Execution evidence describes the execution path and its outcome.

It can preserve information about:

- the requested execution path
- the effective execution path
- execution changes
- provider and model context
- execution outcome

This allows runtime evidence to distinguish between the application's requested execution and the execution that actually occurred.

---

# Determinism

Determinism applies to WAIL's evaluation and decision process.

Given the same runtime evidence, execution state, policy, and control conditions, WAIL produces the same runtime assessment and operational decision.

Execution-specific observations can naturally differ between separate AI requests. Values such as measured latency, timestamps, trace identifiers, hashes, and signatures describe a particular execution and are not expected to be identical across separate executions.

This distinction allows WAIL to preserve real runtime observations while maintaining deterministic assessment and decision behavior.

---

# Standardization

WAIL represents supported AI providers through a consistent runtime evidence model.

Provider-specific execution details are normalized into a common evidence structure so that runtime behavior can be inspected and evaluated consistently across supported providers.

The evidence available in a particular artifact can vary according to execution context and enabled capabilities without changing the underlying evidence model.

---

# Integrity

Runtime evidence includes cryptographic integrity information.

Integrity protection binds the generated artifact to the evidence it contains and allows later modification to be detected.

This makes the evidence suitable for independent verification rather than requiring trust in an unverified runtime log.

---

# Verification

Generated runtime artifacts can be independently verified.

Verification can confirm:

- artifact integrity
- signature validity
- deterministic artifact structure

Artifact structure and verification commands are documented separately in the Runtime Artifact Reference and CLI Reference.

---

# Evidence and Governance

Runtime evidence provides the factual foundation for additional governance capabilities where enabled.

Governance information can build on the same observed execution, assessment, decision, control, and outcome evidence without changing the underlying runtime record.

This separation allows runtime evidence to remain the execution record while governance provides additional lifecycle, obligation, and compliance context.

---

# Summary

The WAIL Runtime Evidence Model defines how observed AI execution is represented as structured, deterministic, and cryptographically verifiable evidence.

It preserves the relationship between runtime observations, assessment, operational decisions, control state, and execution outcome while maintaining a consistent evidence model across supported AI providers.