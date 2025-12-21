"""
Research_Property_Ownership_AU_East

This module searches public property ownership data sources for the eastern
Australian states of Victoria (VIC), Queensland (QLD), and New South Wales (NSW).
It identifies properties owned by the subject, their transaction history, and
parcel IDs. Designed for integration into a modular PI intelligence engine.

- Inherits from IntelModuleBase for validation and logging.
- Accepts a profile object (see schemas/profile_schema.json).
- Writes results to the 'geo' section of the profile using schema-compliant fields.
- Validates input and output.
- Logs all results using the base class logger.

NOTE: This implementation simulates property data lookup for demonstration.
"""

from typing import Any, Dict, List
from core.module_base import IntelModuleBase
import logging

class Research_Property_Ownership_AU_East(IntelModuleBase):
    def __init__(self, logger: logging.Logger = None):
        # Only the 'geo' section will be written to
        # Load the relevant part of the schema for 'geo'
        import json
        with open("schemas/profile_schema.json", "r") as f:
            schema = json.load(f)
        geo_schema = schema["properties"]["geo"]
        super().__init__(
            module_name="Research_Property_Ownership_AU_East",
            profile_schema=schema,      # Validate full profile input
            output_schema={"properties": {"geo": geo_schema}, "required": ["geo"]},
            logger=logger
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        # Extract subject info for property search
        identity = profile.get("identity", {})
        contact = profile.get("contact", {})
        full_name = identity.get("full_name", "")
        addresses = contact.get("addresses", [])

        # Simulate property search for VIC, QLD, NSW
        east_states = [
            {"state_codes": ["VIC", "Victoria"], "parcel_prefix": "VIC", "lat": -37.8136, "lon": 144.9631},
            {"state_codes": ["QLD", "Queensland"], "parcel_prefix": "QLD", "lat": -27.4698, "lon": 153.0251},
            {"state_codes": ["NSW", "New South Wales"], "parcel_prefix": "NSW", "lat": -33.8688, "lon": 151.2093},
        ]

        found_properties: List[Dict[str, Any]] = []
        for addr in addresses:
            state_val = addr.get("state", "").strip().upper()
            for state in east_states:
                if any(code.upper() in state_val or code.upper() in addr.get("state", "").upper() for code in state["state_codes"]):
                    found_properties.append({
                        "address": addr,
                        "parcel_id": f"{state['parcel_prefix']}123456789",
                        "transaction_history": [
                            {
                                "date": "2018-06-15",
                                "type": "purchase",
                                "amount": 850000,
                                "parties": [full_name]
                            },
                            {
                                "date": "2022-01-10",
                                "type": "mortgage",
                                "amount": 500000,
                                "parties": [full_name, f"BigBank {state['parcel_prefix']}"]
                            }
                        ],
                        "lat": state["lat"],
                        "lon": state["lon"]
                    })
                    break

        # Prepare geo section update (schema-compliant)
        geo_section = profile.get("geo", {})
        # Add cities and geo_coordinates for each property found
        cities = geo_section.get("cities", [])
        geo_coordinates = geo_section.get("geo_coordinates", [])

        for prop in found_properties:
            addr = prop["address"]
            city = addr.get("city", "")
            if city and city not in cities:
                cities.append(city)
            geo_coordinates.append({
                "latitude": prop["lat"],
                "longitude": prop["lon"],
                "radius_m": 50
            })

        # Compose output as required by output_schema
        output = {
            "geo": {
                "cities": cities,
                "geo_coordinates": geo_coordinates
            }
        }

        return output

    def execute(self, profile: Dict[str, Any]) -> Any:
        # Standard pipeline: validate input, run, validate output, log
        self._current_profile = profile
        self.validate_input()
        result = self._execute_impl(profile)
        self._last_result = result
        self.validate_output()
        self.log_result()
        return result
