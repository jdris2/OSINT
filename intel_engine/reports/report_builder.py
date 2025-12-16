"""Utilities to generate structured and human-readable PI intelligence reports."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class IntelReportBuilder:
    """Build JSON + Markdown reports for a processed intelligence profile."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Args:
            output_dir: Directory where artifacts will be persisted.
            logger: Optional logger for visibility.
        """
        self.output_dir = (
            Path(output_dir)
            if output_dir
            else Path(__file__).resolve().parent / "output"
        )
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        # Ensure the output folder exists before any export happens.
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_reports(
        self,
        profile: Dict[str, Any],
        field_sources: Optional[Dict[str, Iterable[str]]] = None,
        risk_score: Optional[float] = None,
    ) -> Dict[str, Path]:
        """
        Persist both the raw JSON payload and a formatted Markdown report.

        Args:
            profile: Canonical profile dictionary from the engine.
            field_sources: Mapping of dotted field paths to contributing modules.
            risk_score: Optional override for the exposure score, otherwise
                derived from profile["risk"]["exposure_score"].

        Returns:
            Dictionary containing filesystem paths for generated artifacts.
        """
        if not isinstance(profile, dict):
            raise TypeError("profile must be provided as a dictionary.")

        normalized_sources = self._normalize_sources(field_sources)
        resolved_risk = self._resolve_risk_score(profile, risk_score)

        json_path = self._export_json(profile, normalized_sources, resolved_risk)
        md_path = self._export_markdown(profile, normalized_sources, resolved_risk)
        return {"json": json_path, "markdown": md_path}

    def _export_json(
        self,
        profile: Dict[str, Any],
        field_sources: Dict[str, List[str]],
        risk_score: Optional[float],
    ) -> Path:
        """Serialize the raw profile alongside metadata for traceability."""
        payload = {
            "profile": profile,
            "field_sources": field_sources,
            "risk_score": risk_score,
        }
        output_path = self.output_dir / "profile_report.json"
        output_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        self.logger.info("Wrote JSON report to %s", output_path)
        return output_path

    def _export_markdown(
        self,
        profile: Dict[str, Any],
        field_sources: Dict[str, List[str]],
        risk_score: Optional[float],
    ) -> Path:
        """Create a readable Markdown report summarizing key intelligence."""
        lines = ["# Intelligence Report", ""]
        if risk_score is not None:
            lines.append(f"**Risk Score Total:** {risk_score}")
            lines.append("")

        lines.extend(self._render_identity_section(profile))
        lines.extend(self._render_alias_company_section(profile))
        lines.extend(self._render_geo_and_digital_section(profile))
        lines.extend(self._render_legal_and_risk_section(profile))
        lines.extend(self._render_sources_section(field_sources))

        output_path = self.output_dir / "profile_report.md"
        output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        self.logger.info("Wrote Markdown report to %s", output_path)
        return output_path

    def _render_identity_section(self, profile: Dict[str, Any]) -> List[str]:
        """Summarize the most critical identity fields."""
        identity = profile.get("identity", {})
        lines = ["## Identity Summary"]
        lines.append(f"- Full Name: {identity.get('full_name') or 'Unknown'}")
        lines.append(f"- Date of Birth: {identity.get('dob') or 'Unknown'}")
        lines.append(f"- Gender: {identity.get('gender') or 'Unknown'}")
        primary_address = self._safe_get(profile, ["contact", "addresses"], default=[])
        if primary_address:
            lines.append(f"- Primary Address: {primary_address[0]}")
        else:
            lines.append("- Primary Address: Not provided")
        lines.append("")
        return lines

    def _render_alias_company_section(self, profile: Dict[str, Any]) -> List[str]:
        """Highlight aliases, companies, phones, and social handles."""
        identity = profile.get("identity", {})
        business = profile.get("business", {})
        contact = profile.get("contact", {})
        social = profile.get("social", {})

        aliases = identity.get("aliases") or []
        companies = business.get("company_names") or []
        phones = contact.get("phones") or []
        social_handles = social.get("platforms") or social.get("profile_links") or []

        lines = ["## Known Aliases, Companies, Phones, Socials"]
        lines.append(f"- Aliases: {self._format_list(aliases)}")
        lines.append(f"- Companies: {self._format_list(companies)}")
        lines.append(f"- Phone Numbers: {self._format_list(phones)}")
        lines.append(f"- Social Profiles: {self._format_list(social_handles)}")
        lines.append("")
        return lines

    def _render_geo_and_digital_section(self, profile: Dict[str, Any]) -> List[str]:
        """Combine geographic history with IP/device intelligence."""
        geo = profile.get("geo", {})
        digital = profile.get("digital", {})
        cities = geo.get("cities") or []
        coordinates = geo.get("geo_coordinates") or []
        ips = digital.get("ips") or []
        devices = digital.get("devices") or []

        lines = ["## Geo Summary and Digital Footprint"]
        lines.append(f"- Known Cities: {self._format_list(cities)}")
        lines.append(f"- Geo Coordinates: {self._format_list(coordinates)}")
        lines.append(f"- IP Addresses: {self._format_list(ips)}")
        lines.append(f"- Devices: {self._format_list(devices)}")
        lines.append("")
        return lines

    def _render_legal_and_risk_section(self, profile: Dict[str, Any]) -> List[str]:
        """Outline legal matters and highlight red-flag exposures."""
        legal = profile.get("legal", {})
        risk = profile.get("risk", {})

        bankruptcies = legal.get("bankruptcies") or []
        court_cases = legal.get("court_cases") or []
        sanctions = legal.get("sanctions") or []
        red_flags = risk.get("red_flags") or []

        lines = ["## Legal and Exposure Risks"]
        lines.append(f"- Bankruptcies: {self._format_list(bankruptcies)}")
        lines.append(f"- Court Cases: {self._format_list(court_cases)}")
        lines.append(f"- Sanctions: {self._format_list(sanctions)}")

        if red_flags:
            for flag in red_flags:
                # Prefix red flags so they stand out for analysts during triage.
                lines.append(f"- **[RED FLAG]** {flag}")
        else:
            lines.append("- No explicit red flags recorded.")
        lines.append("")
        return lines

    def _render_sources_section(
        self, field_sources: Dict[str, List[str]]
    ) -> List[str]:
        """List which modules populated each field for auditability."""
        lines = ["## Sources Used"]
        if not field_sources:
            lines.append("No module attribution data was supplied.")
            lines.append("")
            return lines

        lines.append("| Field | Modules |")
        lines.append("| --- | --- |")
        for path, modules in sorted(field_sources.items()):
            modules_display = ", ".join(modules) if modules else "Unknown"
            lines.append(f"| `{path}` | {modules_display} |")
        lines.append("")
        return lines

    def _normalize_sources(
        self, field_sources: Optional[Dict[str, Iterable[str]]]
    ) -> Dict[str, List[str]]:
        """
        Normalize incoming source mappings for consistent downstream handling.
        """
        if not field_sources:
            return {}

        normalized: Dict[str, List[str]] = {}
        for field_path, modules in field_sources.items():
            # Coerce every entry into a list so JSON + Markdown stay consistent.
            if modules is None:
                normalized[field_path] = []
            elif isinstance(modules, str):
                normalized[field_path] = [modules]
            else:
                normalized[field_path] = list(modules)
        return normalized

    def _resolve_risk_score(
        self, profile: Dict[str, Any], explicit_score: Optional[float]
    ) -> Optional[float]:
        """Prefer the explicit score but fall back to the profile payload."""
        if explicit_score is not None:
            return explicit_score
        risk_section = profile.get("risk", {})
        score = risk_section.get("exposure_score")
        return score if isinstance(score, (int, float)) else None

    def _safe_get(
        self, payload: Dict[str, Any], keys: List[str], default: Any = None
    ) -> Any:
        """Walk nested dictionaries/lists safely with a fallback."""
        current: Any = payload
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def _format_list(self, values: Iterable[Any]) -> str:
        """Render iterables as comma-separated strings for Markdown."""
        cleaned = [str(item) for item in values if item not in (None, "")]
        return ", ".join(cleaned) if cleaned else "None"
