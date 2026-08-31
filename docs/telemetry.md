# WAIL Telemetry

WAIL collects limited product-usage telemetry to measure product adoption, usage, and version distribution.

Telemetry is designed to provide basic aggregate insight into how WAIL is being used without collecting application content or customer workload data.

## Data Collected

WAIL may collect the following information:

- Anonymous installation identifier
- WAIL version
- License plan
- Last activity time
- Total WAIL invocation count
- Cumulative active runtime duration
- AI providers used
- AI model names used

The installation identifier is generated locally and is used to distinguish installations without requiring user identity information.

## Data Not Collected

WAIL telemetry does not collect:

- Prompts
- Model responses
- Prompt or response content
- API keys or provider credentials
- Customer application data
- Files or documents processed by customer applications
- Generated runtime evidence

Telemetry is not intended to capture the content of AI workloads.

## Purpose

Telemetry is used to understand:

- WAIL adoption and active usage
- Version distribution
- License plan usage
- Runtime usage levels
- Provider and model adoption

This information helps WAIL Infrastructure evaluate product usage, compatibility, reliability, and future development priorities.

## Transmission

Product-usage telemetry is transmitted periodically to WAIL Infrastructure over HTTPS.

Telemetry is separate from WAIL's runtime control and evidence processing. Telemetry transmission failures do not prevent WAIL from processing runtime requests.

## Privacy

Telemetry is intentionally limited to operational and product-usage metadata.

Prompts, model responses, generated runtime evidence, API credentials, and customer application data are not transmitted as part of product telemetry.

For additional information about how WAIL Infrastructure handles data, refer to the WAIL Privacy Policy.