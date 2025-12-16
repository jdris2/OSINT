"""Planning engine that coordinates module execution based on schema coverage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "profile_schema.json"


class AIPlanner:
    """Plan module execution order by inspecting profile completeness."""

    def __init__(
        self,
        schema: Optional[Dict[str, Any]] = None,
        schema_path: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Args:
            schema: Optional schema dictionary for dependency injection.
            schema_path: Optional filesystem path to the profile schema.
            logger: Optional planner-specific logger.
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        if schema is not None:
            self.schema = schema
        else:
            resolved_path = schema_path or DEFAULT_SCHEMA_PATH
            self.schema = self._load_schema(resolved_path)

        self.section_requirements = self._extract_section_requirements()
        self.section_modules = self._build_module_catalog()

    def _load_schema(self, path: Path) -> Dict[str, Any]:
        """Load the JSON schema from disk."""
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _extract_section_requirements(self) -> Dict[str, List[str]]:
        """Derive the required fields for each top-level section."""
        properties: Dict[str, Dict[str, Any]] = self.schema.get("properties", {})
        return {
            section: definition.get("required", [])
            for section, definition in properties.items()
        }

    def _build_module_catalog(self) -> Dict[str, List[str]]:
        """Map schema sections to the modules that can enrich them."""
        return {
            "identity": ["Identity_DeepDive", "Alias_Expansion"],
            "contact": ["Contact_Network_Map"],
            "digital": ["Digital_Footprint_Audit"],
            "business": ["Research_ABN_Lookup", "Director_Association_Scan"],
            "legal": ["Legal_Proceedings_Scan"],
            "metadata": ["Document_Metadata_Aggregator"],
            "social": ["Social_Temporal_Analysis"],
            "geo": ["Geo_History_Reconstruction"],
            "risk": ["Risk_Scorer"],
        }

    def analyze_gaps(self, profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate the profile and highlight missing schema data per section.

        Returns:
            Dictionary keyed by section name with missing fields and completeness.
        """
        gaps: Dict[str, Dict[str, Any]] = {}
        for section, required_fields in self.section_requirements.items():
            section_payload = profile.get(section)
            missing_fields: List[str] = []

            if section_payload is None:
                missing_fields = list(required_fields) or ["__section_missing__"]
            else:
                for field_name in required_fields:
                    value = section_payload.get(field_name)
                    if value in (None, "", [], {}):
                        missing_fields.append(field_name)

            denominator = max(1, len(required_fields))
            completeness = max(0.0, 1.0 - (len(missing_fields) / denominator))
            gaps[section] = {
                "missing_fields": missing_fields,
                "completeness": completeness,
            }

        return gaps

    def suggest_modules(
        self, profile: Dict[str, Any], history: Optional[Iterable[str]] = None
    ) -> List[Dict[str, float]]:
        """
        Suggest the next set of modules to execute based on profile gaps.

        Args:
            profile: Current working profile.
            history: Iterable of module names that have already executed.

        Returns:
            Ranked list of dictionaries {module_name: score}.
        """
        # Track executed modules to ensure we never re-schedule the same unit.
        executed = {name.lower() for name in (history or [])}
        # Run the gap analysis once so all ranking decisions share the same context.
        gap_summary = self.analyze_gaps(profile)
        suggestions: List[Dict[str, float]] = []

        for section, details in gap_summary.items():
            modules = self.section_modules.get(section, [])
            if not modules:
                continue

            missing_ratio = 1.0 - details["completeness"]
            if missing_ratio <= 0:
                continue

            for rank, module_name in enumerate(modules):
                if module_name.lower() in executed:
                    continue

                # Sections with higher missing_ratio receive higher base scores.
                base_score = missing_ratio * 100
                # Earlier modules per section get a slight bonus to break ties.
                priority_multiplier = max(0.5, 1.0 - (rank * 0.1))
                # Incorporate how many individual fields the module could satisfy.
                field_pressure = 1 + len(details["missing_fields"]) * 0.05
                score = round(base_score * priority_multiplier * field_pressure, 2)

                suggestions.append({module_name: score})

        # Present highest-need modules first so callers can process sequentially.
        suggestions.sort(
            key=lambda item: next(iter(item.values())), reverse=True
        )
        return suggestions
