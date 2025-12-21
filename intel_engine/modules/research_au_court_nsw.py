"""
Research_CourtCases_AU_QLD_NSW

This module searches publicly available court records for Queensland (QLD) and New South Wales (NSW), Australia.
It simulates querying official court databases for filings matching the subject's full name, returning case numbers,
court names, and filing status. Results are written to the 'legal' section of the profile in a schema-compliant format.

Data Source: Publicly listed QLD and NSW court records (simulated for demonstration).
Purpose: To enrich the profile with legal case information relevant to the subject.
"""

from typing import Any, Dict, List
import datetime
import logging
import os
import json

from intel_engine.core.module_base import IntelModuleBase

# Load the output schema for the 'legal' section from the profile schema
def _extract_legal_schema():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schemas", "profile_schema.json")
    with open(schema_path, "r") as f:
        profile_schema = json.load(f)
    return profile_schema["properties"]["legal"]

LEGAL_SCHEMA = _extract_legal_schema()

class Research_CourtCases_AU_QLD_NSW(IntelModuleBase):
    """
    Module to search QLD and NSW court filings by full name and return case numbers, court names, and filing status.
    Results are stored in the 'legal' section of the profile using schema-compliant fields.
    """

    MODULE_NAME = "Research_CourtCases_AU_QLD_NSW"

    def __init__(self, logger: logging.Logger = None) -> None:
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=None,  # Accept any profile, will validate in execute
            output_schema=LEGAL_SCHEMA,
            logger=logger,
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        # Validate input profile using the full profile schema
        # (Base class will call validate_input, but we want to ensure 'identity' and 'legal' exist)
        identity = profile.get("identity", {})
        full_name = identity.get("full_name", "").strip()
        if not full_name:
            raise ValueError("Profile missing 'identity.full_name' required for court case search.")

        # Simulate a search in QLD and NSW court records
        # In a real implementation, this would query APIs or scrape public records
        # Here, we mock results for demonstration
        mock_cases = self._mock_court_search(full_name)

        # Prepare output in schema-compliant format for the 'legal' section
        # Only update 'court_cases', leave other fields as in the input profile
        output_legal = {
            "bankruptcies": profile.get("legal", {}).get("bankruptcies", []),
            "court_cases": mock_cases,
            "sanctions": profile.get("legal", {}).get("sanctions", []),
        }

        return output_legal

    def _mock_court_search(self, full_name: str) -> List[Dict[str, Any]]:
        # For demonstration, return a couple of mock cases if the name is not empty
        today = datetime.date.today().isoformat()
        return [
            {
                "name": f"{full_name} v. State of QLD",
                "jurisdiction": "QLD",
                "role": "Defendant",
                "status": "Open",
                "date": today,
            },
            {
                "name": f"State of NSW v. {full_name}",
                "jurisdiction": "NSW",
                "role": "Plaintiff",
                "status": "Closed",
                "date": (datetime.date.today() - datetime.timedelta(days=365)).isoformat(),
            },
        ]

    def execute(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the module: validate input, run search, validate output, log, and return updated 'legal' section.
        """
        self._current_profile = profile
        # Validate input using the full profile schema
        self.validate_input()
        result = self._execute_impl(profile)
        self._last_result = result
        self.validate_output()
        self.log_result()
        return result
