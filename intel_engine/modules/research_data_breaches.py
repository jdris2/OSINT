"""
Research_Shared_Breaches_HaveIBeenPwned

This module checks if the subject's email(s) appear in known data breaches using the HaveIBeenPwned (HIBP) data source.
It simulates querying HIBP for each email in the profile and reports any breaches found, including what data was leaked
(e.g., passwords, location, etc). Results are stored in the profile's 'risk' section using schema-compliant field names.

- Data Source: https://haveibeenpwned.com/
- Purpose: To identify and summarize data breach exposure for the subject's email addresses.

NOTE: This implementation uses mock breach data for demonstration, as no external API calls are permitted.
"""

from typing import Any, Dict, List
from intel_engine.core.module_base import IntelModuleBase

# Mock breach database for demonstration
MOCK_BREACHES = {
    "alice@example.com": [
        {
            "breach": "ExampleBreach2020",
            "leaked": ["passwords", "location", "phone"],
            "date": "2020-05-01"
        }
    ],
    "bob@example.com": [
        {
            "breach": "AnotherBreach2019",
            "leaked": ["passwords"],
            "date": "2019-11-15"
        },
        {
            "breach": "SampleBreach2018",
            "leaked": ["passwords", "emails"],
            "date": "2018-07-22"
        }
    ]
}

class Research_Shared_Breaches_HaveIBeenPwned(IntelModuleBase):
    """
    Module to check if subject's email(s) appear in known data breaches (HaveIBeenPwned).
    Updates the profile's 'risk' section with breach details and red flags.
    """

    def __init__(self):
        profile_schema = {
            "required": ["contact"],
            "properties": {
                "contact": {
                    "type": "object",
                    "required": ["emails"],
                    "properties": {
                        "emails": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            }
        }
        # Output schema: only the 'risk' section, as per profile_schema.json
        output_schema = {
            "required": ["risk"],
            "properties": {
                "risk": {
                    "type": "object",
                    "required": ["exposure_score", "red_flags"],
                    "properties": {
                        "exposure_score": {"type": "number"},
                        "red_flags": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "category": {"type": "string"},
                                    "description": {"type": "string"},
                                    "severity": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            }
        }
        super().__init__(
            module_name="Research_Shared_Breaches_HaveIBeenPwned",
            profile_schema=profile_schema,
            output_schema=output_schema
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        emails: List[str] = profile.get("contact", {}).get("emails", [])
        breaches_found = []
        red_flags = []
        exposure_score = 0

        for email in emails:
            breaches = MOCK_BREACHES.get(email.lower(), [])
            for breach in breaches:
                breaches_found.append({
                    "email": email,
                    "breach": breach["breach"],
                    "leaked": breach["leaked"],
                    "date": breach["date"]
                })
                # Add a red flag for each breach
                red_flags.append({
                    "category": "data_breach",
                    "description": (
                        f"Email {email} found in breach '{breach['breach']}' "
                        f"on {breach['date']} (leaked: {', '.join(breach['leaked'])})"
                    ),
                    "severity": "high" if "passwords" in breach["leaked"] else "medium"
                })
                # Increase exposure score for each breach
                exposure_score += 20 if "passwords" in breach["leaked"] else 10

        # Cap exposure_score at 100
        exposure_score = min(exposure_score, 100)

        # If no breaches, set a low exposure score and empty red_flags
        if not breaches_found:
            exposure_score = 5
            red_flags = []

        # Compose output as required by output_schema
        output = {
            "risk": {
                "exposure_score": exposure_score,
                "red_flags": red_flags
            }
        }
        return output
