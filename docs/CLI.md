# WAIL CLI

WAIL includes a command-line interface for inspecting runtime state, licenses, audit artifacts, incidents, and forensic traces.

Run commands using the installed WAIL CLI:

```bash
wail <command>
```

The CLI can also be invoked through Python:

```bash
python -m wail.cli <command>
```

The examples below use the `wail` command.

---

## Version

Display the installed WAIL engine, schema, and policy versions.

```bash
wail version
```

---

## License Status

Display the current license status and runtime limits.

```bash
wail license status
```

Shows:

- License validity
- Active plan
- Customer
- Expiration date
- Maximum active runtimes
- License security violation status

---

## Runtime Status

Display the current persisted WAIL runtime state.

```bash
wail runtime-status
```

Shows:

- State hash
- Policy version
- Segment limit
- Segment count
- Schema version

---

## List Runtime Incidents

List traces where WAIL detected or performed a runtime intervention.

```bash
wail traces incidents
```

The output includes the trace ID, decision, severity, and provider transition when execution was rerouted.

---

## Inspect a Trace

Inspect a specific runtime trace.

```bash
wail trace show <TRACE_ID>
```

Example:

```bash
wail trace show 01M00N3XWMYJEWB9WVPDE66CXF
```

The trace view includes execution target information, runtime context, recommendations, pre-incident information, and available investigation paths.

### Raw Trace

Display the underlying trace data:

```bash
wail trace show <TRACE_ID> --raw
```

### Full Forensic Stream

Display the full stored forensic stream when available:

```bash
wail trace show <TRACE_ID> --full-stream
```

---

## Verify an Audit Artifact

Verify the cryptographic integrity and signature of a WAIL audit artifact.

```bash
wail verify <ARTIFACT_FILE>
```

A successful verification reports:

- Status: `VALID`
- Signature: `VERIFIED`
- Integrity: `PASSED`

---

## Replay a Trace

Replay WAIL analysis from an existing trace.

Using a trace ID:

```bash
wail replay <TRACE_ID>
```

Using an artifact file:

```bash
wail replay --file <ARTIFACT_FILE>
```

Replay is intended for deterministic inspection of previously recorded runtime evidence.

---

## Command Reference

| Task | Command |
|---|---|
| Show WAIL version | `wail version` |
| Show license status | `wail license status` |
| Show runtime state | `wail runtime-status` |
| List runtime incidents | `wail traces incidents` |
| Inspect a trace | `wail trace show <TRACE_ID>` |
| Inspect raw trace | `wail trace show <TRACE_ID> --raw` |
| Inspect forensic stream | `wail trace show <TRACE_ID> --full-stream` |
| Verify an artifact | `wail verify <ARTIFACT_FILE>` |
| Replay by trace ID | `wail replay <TRACE_ID>` |
| Replay by artifact | `wail replay --file <ARTIFACT_FILE>` |