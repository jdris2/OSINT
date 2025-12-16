"""Module that simulates ABN lookups against a deterministic mock service."""

from __future__ import annotations

import logging
from datetime import date
from hashlib import sha256
from typing import Any, Dict, Optional

from intel_engine.core.module_base import IntelModuleBase


class ResearchABNLookup(IntelModuleBase):
    """Perform synthetic ABN lookups based on a profile's identity data."""

    MODULE_NAME = "Research_ABN_Lookup"
    PROFILE_SCHEMA = {
        "type": "object",
        "properties": {
            "identity": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "minLength": 1},
                },
            },
            "business": {
                "type": "object",
                "properties": {
                    "company_names": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    }
                },
            },
        },
        "required": [],
    }

    OUTPUT_SCHEMA = {
        "type": "object",
        "required": ["business"],
        "properties": {
            "business": {
                "type": "object",
                "required": [
                    "abn",
                    "entity_name",
                    "registration_date",
                    "status",
                    "state",
                    "gst_status",
                ],
                "properties": {
                    "abn": {"type": "string", "minLength": 11},
                    "entity_name": {"type": "string"},
                    "registration_date": {"type": "string"},
                    "status": {"type": "string"},
                    "state": {"type": "string"},
                    "gst_status": {
                        "type": "string",
                        "enum": ["registered", "not_registered", "unknown"],
                    },
                },
            }
        },
    }

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=self.PROFILE_SCHEMA,
            output_schema=self.OUTPUT_SCHEMA,
            logger=logger,
        )

    def validate_input(self) -> None:
        """Extend validation to ensure at least one lookup target is present."""
        super().validate_input()
        profile = self._current_profile or {}
        name = profile.get("identity", {}).get("full_name")
        business_names = profile.get("business", {}).get("company_names") or []
        if not name and not business_names:
            raise ValueError(
                "Research_ABN_Lookup requires either an identity.full_name "
                "or business.company_names entry."
            )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the deterministic lookup and return the enriched business data."""
        target = self._select_search_target(profile)
        self.logger.debug("Performing mock ABN lookup for '%s'.", target)
        lookup = self._mock_abn_lookup(target)

        business_section = profile.setdefault("business", {})
        business_section.update(lookup)
        self.logger.debug("Updated profile business section with ABN payload.")

        return {"business": lookup}

    def _select_search_target(self, profile: Dict[str, Any]) -> str:
        """Choose which profile identifier should be used for the lookup."""
        business_names = profile.get("business", {}).get("company_names") or []
        if business_names:
            return business_names[0]

        name = profile.get("identity", {}).get("full_name")
        if not name:
            raise ValueError("Unable to determine a subject name for ABN lookup.")
        return name

    def _mock_abn_lookup(self, query: str) -> Dict[str, str]:
        """
        Simulate a stable ABN lookup to allow deterministic testing.

        The function hashes the query to derive pseudo ABN values so repeated runs
        yield the same results without any network calls.
        """
        digest = sha256(query.encode("utf-8")).hexdigest()
        abn_digits = "".join(str(int(char, 16) % 10) for char in digest[:11])

        year = 1990 + (int(digest[11:13], 16) % 30)
        month = (int(digest[13:15], 16) % 12) + 1
        day = (int(digest[15:17], 16) % 28) + 1
        registration_date = date(year, month, day).isoformat()

        states = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"]
        statuses = ["active", "cancelled", "pending"]
        gst_statuses = ["registered", "not_registered", "unknown"]

        state = states[int(digest[17:19], 16) % len(states)]
        status = statuses[int(digest[19:21], 16) % len(statuses)]
        gst_status = gst_statuses[int(digest[21:23], 16) % len(gst_statuses)]

        entity_name = f"{query.strip()} Holdings".strip()

        return {
            "abn": abn_digits,
            "entity_name": entity_name,
            "registration_date": registration_date,
            "status": status,
            "state": state,
            "gst_status": gst_status,
        }
