# Prompt 14 — Public code-repo exposure (GitHub search)

**File:** `intel_engine/modules/research_code_repo_exposure.py`  
**Module/Class:** `Research_CodeRepo_Exposure_GitHub`  
**Purpose:** Find public mentions of target emails/usernames/domains in GitHub code/search results.

## Data sources

- GitHub REST search APIs (rate-limited).

## API key (optional, free)

- `GITHUB_TOKEN` env var: if present, use it; otherwise unauthenticated and enforce strict throttling.

## Inputs

- `contact.emails`, `contact.usernames`, `digital.domains`

## Outputs

- `enrichment.raw_results` (`type: "github_search"`) with repo URLs + file paths + snippet hashes (do not store full file bodies).
- If you detect exposed secret-like patterns, add `risk.red_flags` with conservative wording (“possible secret pattern”), severity `medium`, and evidence link.

## Implementation requirements

- Respect GitHub rate limits; implement exponential backoff for 403/429.
- Never store access tokens in logs.

