# Prompt 13 — Entity/link graph builder (schema-safe)

**File:** `intel_engine/modules/research_entity_graph_builder.py`  
**Module/Class:** `Research_Entity_Graph_Builder`  
**Purpose:** Build a relationship graph without adding new root keys.

## Inputs

- `contact.emails`, `contact.phones`, `contact.usernames`
- `digital.domains`, `digital.ips`
- `social.profile_links`
- `business.company_names`
- `legal.sanctions`

## Outputs

- `enrichment.correlations` (schema-defined) as edges: `identifier`, `source`, `field`, `confidence`
- `enrichment.signals.associations` for human-readable associations
- Store full node/edge list into `enrichment.raw_results` with `type: "entity_graph"`

## Implementation requirements

- Confidence should be conservative; don’t “merge” identities without evidence.
- Avoid exploding graphs; cap nodes/edges and record truncation in raw results.

