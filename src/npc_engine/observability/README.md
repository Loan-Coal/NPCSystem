# Staging Observability Definitions

This directory contains P5 staging observability artifacts.

## Files
- staging_dashboard.json: dashboard panel and metric grouping definitions.
- staging_alert_rules.yaml: threshold rules for staging alerts.

## Scope
- Uses bounded-cardinality labels only.
- High-cardinality values (request_id, npc_id, player_id) stay in structured logs.
- Metric names align with v1.4 P5 tracker requirements.
