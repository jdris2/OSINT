"""
Research_AI_Collection_Orchestrator

Intelligent module sequencer that selects and runs OSINT modules based on
investigation objectives and target signals, aggregating results into a
single orchestration record. This module coordinates other modules without
duplicating their internal logic.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from intel_engine.core.module_base import IntelModuleBase


def _load_profile_schema() -> Dict[str, Any]:
    candidate_paths = [
        Path(__file__).resolve().parents[1] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "profile_schema.json",
    ]
    schema_payload: Optional[Dict[str, Any]] = None
    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                schema_payload = json.load(handle)
            break
    if not schema_payload:
        raise FileNotFoundError(
            "Unable to locate schemas/profile_schema.json for validation."
        )
    return schema_payload


def _build_input_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    properties = {}
    for key in (
        "identity",
        "contact",
        "digital",
        "business",
        "social",
        "metadata",
        "geo",
        "risk",
        "legal",
    ):
        definition = schema_payload.get("properties", {}).get(key)
        if definition:
            properties[key] = definition
    return {"type": "object", "properties": properties}


def _build_orchestration_output_schema(
    schema_payload: Dict[str, Any]
) -> Dict[str, Any]:
    orchestration_schema = schema_payload.get("properties", {}).get("orchestration")
    if not orchestration_schema:
        raise ValueError(
            "profile_schema.json does not define an orchestration section."
        )
    return {
        "type": "object",
        "required": ["orchestration"],
        "properties": {"orchestration": orchestration_schema},
    }


PROFILE_SCHEMA_PAYLOAD = _load_profile_schema()


class ResearchAICollectionOrchestrator(IntelModuleBase):
    """Select and orchestrate OSINT modules based on objectives and targets."""

    MODULE_NAME = "Research_AI_Collection_Orchestrator"
    PROFILE_SCHEMA = _build_input_schema(PROFILE_SCHEMA_PAYLOAD)
    OUTPUT_SCHEMA = _build_orchestration_output_schema(PROFILE_SCHEMA_PAYLOAD)

    MODULE_PRIORITY = [
        "theHarvester",
        "Recon-ng",
        "SpiderFoot",
        "Photon",
        "Metagoofil",
        "Sherlock",
        "GHunt",
        "Skiptracer",
        "Twint",
    ]

    MODULE_REGISTRY = {
        "theHarvester": [
            {
                "import_path": "intel_engine.modules.research_domain_email_enumeration",
                "class_name": "Research_Domain_Email_Enumeration",
                "profile_section": "digital",
            }
        ],
        "SpiderFoot": [
            {
                "import_path": "intel_engine.modules.research_automation_spiderfoot",
                "class_name": "Research_Automation_SpiderFoot",
                "profile_section": "digital",
            }
        ],
        "Recon-ng": [
            {
                "import_path": "intel_engine.modules.research_framework_reconng",
                "class_name": "Research_Framework_ReconNG",
                "profile_section": "intelligence",
            }
        ],
        "Metagoofil": [
            {
                "import_path": "intel_engine.modules.research_metadata_document",
                "class_name": "Research_Metadata_Document_Extraction",
                "profile_section": "digital",
            }
        ],
        "Photon": [
            {
                "import_path": "intel_engine.modules.research_web_crawling_photon",
                "class_name": "ResearchWebCrawlingPhoton",
                "profile_section": "digital",
            },
            {
                "import_path": "intel_engine.modules.research_web_crawling_photon",
                "class_name": "Research_Web_Crawling_Photon",
                "profile_section": "digital",
            },
        ],
        "Sherlock": [
            {
                "import_path": "intel_engine.modules.research_identity_username_search",
                "class_name": "Research_Identity_Username_Search",
                "profile_section": "social",
            }
        ],
        "GHunt": [
            {
                "import_path": "intel_engine.modules.research_account_google_intel",
                "class_name": "ResearchAccountGoogleIntel",
                "profile_section": "digital",
            }
        ],
        "Skiptracer": [
            {
                "import_path": "intel_engine.modules.research_enrichment_skiptracer",
                "class_name": "Research_Enrichment_Skiptracer",
                "profile_section": "enrichment",
            }
        ],
        "Twint": [
            {
                "import_path": "intel_engine.modules.research_social_twitter_intelligence",
                "class_name": "ResearchSocialTwitterIntelligence",
                "profile_section": "social",
            },
            {
                "import_path": "intel_engine.modules.research_twitter_activity",
                "class_name": "ResearchSocialTwitterActivity",
                "profile_section": "social",
            },
        ],
    }

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=self.PROFILE_SCHEMA,
            output_schema=self.OUTPUT_SCHEMA,
            logger=logger,
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        started_at = datetime.utcnow()

        objectives = self._extract_objectives(profile)
        targets = self._extract_targets(profile)
        selected_modules = self._select_modules(objectives, targets)
        execution_order = self._build_execution_order(selected_modules)

        module_results = []
        for module_id in execution_order:
            result_entry = self._run_module(module_id, profile)
            module_results.append(result_entry)

        completed_at = datetime.utcnow()
        duration_s = (completed_at - started_at).total_seconds()

        orchestration = {
            "objectives": objectives,
            "selected_modules": selected_modules,
            "execution_order": execution_order,
            "module_results": module_results,
            "state": {
                "started_at": started_at.isoformat() + "Z",
                "completed_at": completed_at.isoformat() + "Z",
                "duration_s": duration_s,
            },
        }

        profile["orchestration"] = orchestration
        return {"orchestration": orchestration}

    def _extract_objectives(self, profile: Dict[str, Any]) -> List[str]:
        metadata = profile.get("metadata", {})
        documents = metadata.get("documents") or []
        objectives = []
        for doc in documents:
            name = (doc.get("name") or "").strip()
            doc_type = (doc.get("type") or "").strip().lower()
            if doc_type.startswith("objective") or doc_type == "goal":
                if name:
                    objectives.append(name)
                continue
            lowered = name.lower()
            if lowered.startswith("objective:") or lowered.startswith("goal:"):
                objectives.append(name.split(":", 1)[1].strip() or name)
        if not objectives:
            objectives = ["general_osint_collection"]
        return objectives

    def _extract_targets(self, profile: Dict[str, Any]) -> Dict[str, List[str]]:
        identity = profile.get("identity", {})
        contact = profile.get("contact", {})
        digital = profile.get("digital", {})
        business = profile.get("business", {})

        targets = {
            "names": [identity.get("full_name")] if identity.get("full_name") else [],
            "aliases": list(identity.get("aliases") or []),
            "emails": list(contact.get("emails") or []),
            "phones": list(contact.get("phones") or []),
            "usernames": list(contact.get("usernames") or []),
            "domains": list(digital.get("domains") or []),
            "ips": list(digital.get("ips") or []),
            "company_names": list(business.get("company_names") or []),
        }
        return targets

    def _select_modules(
        self, objectives: List[str], targets: Dict[str, List[str]]
    ) -> List[str]:
        selected = set()
        keyword_map = {
            "email": ["theHarvester", "GHunt"],
            "domain": ["theHarvester", "Photon", "Recon-ng", "SpiderFoot"],
            "subdomain": ["theHarvester", "Photon"],
            "social": ["Sherlock", "Twint"],
            "username": ["Sherlock", "Twint"],
            "twitter": ["Twint"],
            "google": ["GHunt"],
            "account": ["GHunt", "Sherlock"],
            "recon": ["theHarvester", "Recon-ng"],
            "crawl": ["Photon"],
            "web": ["Photon", "Metagoofil"],
            "document": ["Metagoofil"],
            "file": ["Metagoofil"],
            "metadata": ["Metagoofil"],
            "infrastructure": ["SpiderFoot"],
            "ip": ["SpiderFoot"],
            "phone": ["Skiptracer"],
            "enrichment": ["Skiptracer"],
            "correlate": ["Recon-ng", "SpiderFoot"],
            "map": ["SpiderFoot"],
        }

        for objective in objectives:
            lowered = objective.lower()
            for keyword, modules in keyword_map.items():
                if keyword in lowered:
                    selected.update(modules)

        if targets.get("emails"):
            selected.update(["theHarvester", "GHunt"])
        if targets.get("domains"):
            selected.update(["theHarvester", "Photon", "Recon-ng", "SpiderFoot"])
        if targets.get("ips"):
            selected.update(["SpiderFoot"])
        if targets.get("usernames"):
            selected.update(["Sherlock", "Twint"])
        if targets.get("phones"):
            selected.update(["Skiptracer"])

        if not selected:
            selected.update(["theHarvester", "Sherlock", "Twint"])

        return self._order_modules(list(selected))

    def _order_modules(self, modules: List[str]) -> List[str]:
        ordered = []
        remaining = set(modules)
        for name in self.MODULE_PRIORITY:
            if name in remaining:
                ordered.append(name)
                remaining.remove(name)
        for name in sorted(remaining):
            ordered.append(name)
        return ordered

    def _build_execution_order(self, selected_modules: List[str]) -> List[str]:
        dependencies = {
            "Recon-ng": ["theHarvester"],
            "SpiderFoot": ["theHarvester", "Recon-ng"],
            "Photon": ["theHarvester"],
            "Metagoofil": ["Photon"],
            "GHunt": [],
            "Sherlock": [],
            "Skiptracer": [],
            "Twint": [],
            "theHarvester": [],
        }

        expanded = set(selected_modules)
        changed = True
        while changed:
            changed = False
            for module_id in list(expanded):
                for dependency in dependencies.get(module_id, []):
                    if dependency not in expanded:
                        expanded.add(dependency)
                        changed = True

        ordered = []
        visiting = set()
        visited = set()

        def visit(module_id: str) -> None:
            if module_id in visited:
                return
            if module_id in visiting:
                self.logger.warning(
                    "Detected dependency cycle for module '%s'.", module_id
                )
                return
            visiting.add(module_id)
            for dependency in dependencies.get(module_id, []):
                if dependency in expanded:
                    visit(dependency)
            visiting.remove(module_id)
            visited.add(module_id)
            ordered.append(module_id)

        for module_id in self._order_modules(list(expanded)):
            visit(module_id)

        return ordered

    def _run_module(self, module_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        module_class, profile_section = self._load_module_class(module_id)
        if not module_class:
            return {
                "module": module_id,
                "status": "unavailable",
                "summary": "Module implementation not found.",
                "profile_section": profile_section,
                "output_keys": [],
            }

        try:
            kwargs, skip_reason = self._prepare_module_kwargs(module_id, profile)
            if skip_reason:
                return {
                    "module": module_id,
                    "status": "skipped",
                    "summary": skip_reason,
                    "profile_section": profile_section,
                    "output_keys": [],
                }
            instance = module_class(**kwargs)
            output = instance.execute(profile)
            output_keys = list(output.keys()) if isinstance(output, dict) else []
            return {
                "module": module_id,
                "status": "completed",
                "summary": "Module executed successfully.",
                "profile_section": profile_section,
                "output_keys": output_keys,
            }
        except Exception as exc:
            self.logger.error("Module '%s' failed: %s", module_id, exc)
            return {
                "module": module_id,
                "status": "failed",
                "summary": str(exc),
                "profile_section": profile_section,
                "output_keys": [],
            }

    def _prepare_module_kwargs(
        self, module_id: str, profile: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        kwargs: Dict[str, Any] = {"logger": self.logger}
        if module_id != "Recon-ng":
            return kwargs, None

        target_type, target_value = self._derive_reconng_target(profile)
        if not target_value or not target_type:
            return {}, "No suitable target found for Recon-ng execution."

        workspace_name = self._build_workspace_name(target_value)
        kwargs.update(
            {
                "workspace_name": workspace_name,
                "target": target_value,
                "target_type": target_type,
            }
        )
        return kwargs, None

    def _derive_reconng_target(
        self, profile: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        digital = profile.get("digital", {})
        domains = digital.get("domains") or []
        if domains:
            return "domain", str(domains[0])

        business = profile.get("business", {})
        company_names = business.get("company_names") or []
        if company_names:
            return "company", str(company_names[0])

        contact = profile.get("contact", {})
        emails = contact.get("emails") or []
        if emails:
            return "contact", str(emails[0])
        phones = contact.get("phones") or []
        if phones:
            return "contact", str(phones[0])

        identity = profile.get("identity", {})
        full_name = identity.get("full_name")
        if full_name:
            return "contact", str(full_name)

        return None, None

    def _build_workspace_name(self, target_value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", target_value).strip("_")
        if not cleaned:
            cleaned = "target"
        cleaned = cleaned[:32]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"orchestrator_{cleaned}_{timestamp}"

    def _load_module_class(
        self, module_id: str
    ) -> Tuple[Optional[type], str]:
        candidates = self.MODULE_REGISTRY.get(module_id, [])
        if not candidates:
            return None, "unknown"
        for candidate in candidates:
            try:
                module = importlib.import_module(candidate["import_path"])
                module_class = getattr(module, candidate["class_name"])
                return module_class, candidate["profile_section"]
            except Exception:
                continue
        return None, candidates[0]["profile_section"]


class Research_AI_Collection_Orchestrator(ResearchAICollectionOrchestrator):
    """Compatibility alias for the orchestrator module class."""
