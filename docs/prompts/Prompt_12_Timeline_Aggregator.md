# Prompt 12 — Timeline aggregator (schema-safe)

**File:** `intel_engine/modules/research_timeline_aggregator.py`  
**Module/Class:** `Research_Timeline_Aggregator`  
**Purpose:** Create a unified timeline from everything already in the profile without adding a new top-level `timeline` key.

## Inputs

- Use existing sections: `legal.court_cases` dates, `metadata.documents.created`, `social.last_activity.timestamp`, and timestamps inside `enrichment.raw_results` payloads when present.

## Outputs

- Store assembled timeline array into `enrichment.raw_results` with `type: "timeline"` and `payload: {"events": [...]}`.
- Each event includes: `timestamp`, `source`, `summary`, `confidence`, `evidence` (urls/ids).

## Implementation requirements

- Sort chronologically; keep provenance for every event.
- De-duplicate identical events.

