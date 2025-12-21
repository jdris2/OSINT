"""
Research_Phone_Number_Metadata Module

Data Source:
  - Uses the NumVerify API (https://numverify.com/) to perform real-time phone number metadata lookups.
  - For each phone number in the profile, resolves country, carrier, and type (mobile/landline/VOIP).
  - Requires a valid NumVerify API key set in the environment variable NUMVERIFY_API_KEY.

Purpose:
  - Enriches the profile's contact section with phone metadata for each phone number.
  - Stores results in profile['contact']['phone_metadata'] as a list of objects, schema-compliant.
  - Validates input and output using the profile schema.
  - Logs all inputs and results using the .log_result() method from IntelModuleBase.
"""

import os
import logging
import requests
from typing import Any, Dict, List, Optional

from intel_engine.core.module_base import IntelModuleBase

class Research_Phone_Number_Metadata(IntelModuleBase):
    MODULE_NAME = "Research_Phone_Number_Metadata"

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        import json
        from pathlib import Path
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "profile_schema.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        # Only validate the 'contact' section
        contact_schema = {
            "type": "object",
            "required": ["contact"],
            "properties": {
                "contact": schema["properties"]["contact"]
            }
        }
        # Output schema: contact section with phone_metadata
        output_schema = {
            "type": "object",
            "required": ["contact"],
            "properties": {
                "contact": {
                    "type": "object",
                    "properties": {
                        **schema["properties"]["contact"]["properties"],
                        "phone_metadata": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "phone": {"type": "string"},
                                    "country": {"type": "string"},
                                    "carrier": {"type": "string"},
                                    "type": {"type": "string", "enum": ["mobile", "landline", "voip", "unknown"]}
                                },
                                "required": ["phone", "country", "carrier", "type"]
                            }
                        }
                    }
                }
            }
        }
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=contact_schema,
            output_schema=output_schema,
            logger=logger,
        )
        self.api_key = os.environ.get("NUMVERIFY_API_KEY")
        if not self.api_key:
            raise RuntimeError("NUMVERIFY_API_KEY environment variable is not set.")

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        self.log_result()  # Log input

        contact = profile.get("contact", {})
        phones = contact.get("phones", [])
        phone_metadata: List[Dict[str, str]] = []

        for phone in phones:
            meta = self._lookup_phone_metadata(phone)
            phone_metadata.append(meta)

        # Store results in contact['phone_metadata']
        contact = dict(contact)
        contact["phone_metadata"] = phone_metadata

        result = {"contact": contact}
        self._last_result = result
        self.log_result()  # Log output
        return result

    def _lookup_phone_metadata(self, phone: str) -> Dict[str, str]:
        url = "http://apilayer.net/api/validate"
        params = {
            "access_key": self.api_key,
            "number": phone,
            "format": 1
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            # Fallback to unknown if API fails
            return {
                "phone": phone,
                "country": "Unknown",
                "carrier": "Unknown",
                "type": "unknown"
            }

        country = data.get("country_name") or "Unknown"
        carrier = data.get("carrier") or "Unknown"
        line_type = data.get("line_type") or "unknown"
        # Normalize type to schema enum
        if line_type not in {"mobile", "landline", "voip"}:
            line_type = "unknown"

        return {
            "phone": phone,
            "country": country,
            "carrier": carrier,
            "type": line_type
        }
