# AI Observability & Telemetry — WarrantyOS Part 2.6

## Overview

Part 2.6 introduces stage-level execution tracking, cost/latency telemetry, and privacy-preserving structured logging across the AI pipeline.

## Execution Telemetry Fields (`ai_executions`)

| Field | Type | Description |
|---|---|---|
| `execution_id` | String | Unique execution identifier (e.g. `AI-12-3F8A19B2`) |
| `requested_provider` | String | Configured target provider |
| `actual_provider` | String | Provider that executed analysis (`mock`, `rocketride`, `local`) |
| `fallback_used` | Boolean | True if fallback was triggered due to vendor SDK unavailability |
| `fallback_reason` | String | Reason for fallback (e.g. `SDK_NOT_AVAILABLE`) |
| `duration_ms` / `latency_ms` | Integer | Total end-to-end execution duration in milliseconds |
| `input_token_count` | Integer | Estimated input token count |
| `output_token_count` | Integer | Estimated output token count |
| `estimated_cost` | Numeric | Estimated execution cost in USD |

## Stage-Level Tracking (`ai_execution_stages`)

Every execution logs discrete execution timing and status for all 8 pipeline stages:
1. `DOCUMENT_EXTRACTION`
2. `POLICY_CHECK`
3. `EVIDENCE_ANALYSIS`
4. `SIMILAR_CASE_SEARCH`
5. `RISK_ASSESSMENT`
6. `DECISION_AGENT`
7. `VALIDATOR`
8. `GOVERNANCE`

## Privacy & Security Boundaries

Structured logs and telemetry payloads **NEVER** contain:
- Customer email addresses or phone numbers
- Passwords or bcrypt hashes
- JWT tokens or API secrets
- Local filesystem upload paths or invoice raw image binary data
