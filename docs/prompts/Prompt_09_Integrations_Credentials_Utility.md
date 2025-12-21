# Prompt 09 — Free-key integrations config (shared utility)

**File:** `intel_engine/integrations/credentials.py`  
**Purpose:** Centralize env var reads + validation so modules are consistent.

## Requirements

- Provide:
  - `get_env(name: str, required: bool = False, default: str | None = None) -> str | None`
  - `require_env(name: str) -> str` raising `RuntimeError` with a clear message
  - `redact(value: str) -> str` for safe logging
- No third-party dependencies.
- Apply this helper to keyed modules above (ABR_GUID, TROVE_API_KEY, AUSTENDER_API_KEY, optional `GITHUB_TOKEN`).

