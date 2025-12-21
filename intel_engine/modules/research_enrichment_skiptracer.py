"""
Research_Enrichment_Skiptracer

Data Source:
  - Uses the Skiptracer framework (https://github.com/xillwillx/skiptracer)
    to enrich identity signals from emails, phone numbers, and usernames.

Purpose:
  - Aggregates breach, social, and public-record signals into profile['enrichment']
    for deep identity enrichment with confidence scoring and risk context.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from intel_engine.core.module_base import IntelModuleBase

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_PHONE_PATTERN = re.compile(r"^\+?[0-9]{5,}$")
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{2,}$")
_DATE_FIELDS = ("date", "last_seen", "updated", "updated_at", "timestamp")

_PLUGIN_SPECS = [
    {
        "name": "HaveIBeenPwned",
        "category": "breach",
        "types": ("email",),
        "module": "skiptracer.plugins.haveibeenpwned",
        "class": "HaveIBeenPwwnedGrabber",
        "arg_order": "value_type",
    },
    {
        "name": "WhoisMind",
        "category": "public_records",
        "types": ("email",),
        "module": "skiptracer.plugins.whoismind",
        "class": "WhoisMindGrabber",
        "arg_order": "value_type",
    },
    {
        "name": "NameChk",
        "category": "social",
        "types": ("email",),
        "module": "skiptracer.plugins.namechk2",
        "class": "NameChkGrabber",
        "arg_order": "value_type",
    },
    {
        "name": "Knowem",
        "category": "social",
        "types": ("username",),
        "module": "skiptracer.plugins.knowem",
        "class": "KnowemGrabber",
        "arg_order": "value_type",
    },
    {
        "name": "WhoCallId",
        "category": "public_records",
        "types": ("phone",),
        "module": "skiptracer.plugins.who_call_id",
        "class": "WhoCallIdGrabber",
        "arg_order": "value_type",
    },
    {
        "name": "TruePeopleSearch",
        "category": "public_records",
        "types": ("phone", "email", "username"),
        "module": "skiptracer.plugins.true_people",
        "class": "TruePeopleGrabber",
        "arg_order": "value_type",
    },
    {
        "name": "TruthFinder",
        "category": "public_records",
        "types": ("phone", "email", "username"),
        "module": "skiptracer.plugins.truthfinder",
        "class": "TruthFinderGrabber",
        "arg_order": "type_value",
    },
]

_CATEGORY_CONFIDENCE = {
    "breach": 0.6,
    "social": 0.7,
    "public_records": 0.65,
    "unknown": 0.4,
}


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
    contact_schema = schema_payload.get("properties", {}).get("contact")
    return {
        "type": "object",
        "required": ["contact"],
        "properties": {"contact": contact_schema} if contact_schema else {},
    }


def _build_output_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    enrichment_schema = schema_payload.get("properties", {}).get("enrichment")
    if not enrichment_schema:
        raise ValueError("profile_schema.json does not define an enrichment section.")
    return {
        "type": "object",
        "required": ["enrichment"],
        "properties": {"enrichment": enrichment_schema},
    }


def _normalize_email(value: str) -> Tuple[str, bool]:
    cleaned = value.strip().lower()
    return cleaned, bool(_EMAIL_PATTERN.match(cleaned))


def _normalize_phone(value: str) -> Tuple[str, bool]:
    cleaned = re.sub(r"[\\s\\-()]", "", value.strip())
    return cleaned, bool(_PHONE_PATTERN.match(cleaned))


def _normalize_username(value: str) -> Tuple[str, bool]:
    cleaned = value.strip().lstrip("@")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "", cleaned)
    return cleaned, bool(_USERNAME_PATTERN.match(cleaned))


def _infer_identifier(value: str) -> Tuple[str, str, bool]:
    email, email_ok = _normalize_email(value)
    if email_ok:
        return "email", email, True
    phone, phone_ok = _normalize_phone(value)
    if phone_ok:
        return "phone", phone, True
    username, username_ok = _normalize_username(value)
    return "username", username, username_ok


def _walk_payload(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_payload(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_payload(item)


def _extract_timestamp(payload: Any) -> List[datetime]:
    timestamps: List[datetime] = []
    for node in _walk_payload(payload):
        for key, value in node.items():
            if not isinstance(value, str):
                continue
            lowered = key.lower()
            if any(field in lowered for field in _DATE_FIELDS):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
                timestamps.append(parsed)
    return timestamps


def _ensure_skiptracer_on_path() -> bool:
    if importlib.util.find_spec("skiptracer") is not None:
        return True

    candidate_roots = []
    env_path = os.environ.get("SKIPTRACER_REPO") or os.environ.get("SKIPTRACER_PATH")
    if env_path:
        candidate_roots.append(Path(env_path))

    candidate_roots.append(Path(__file__).resolve().parents[2] / "skiptracer")

    for root in candidate_roots:
        src_path = root / "src"
        if src_path.exists() and src_path.is_dir():
            sys.path.insert(0, str(src_path))
            if importlib.util.find_spec("skiptracer") is not None:
                return True
    return False


def _prepare_skiptracer_globals() -> None:
    try:
        import builtins as bi
    except ImportError:
        return

    defaults = {
        "search_string": None,
        "lookup": None,
        "output": None,
        "outdata": {},
        "webproxy": None,
        "proxy": None,
        "debug": False,
    }
    for key, value in defaults.items():
        if not hasattr(bi, key):
            setattr(bi, key, value)


def _load_plugin_class(module_path: str, class_name: str) -> Optional[type]:
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return None
    return getattr(module, class_name, None)


def _collect_plugin_payload(instance: Any, output: Any) -> Any:
    if output is not None:
        return output
    info_dict = getattr(instance, "info_dict", None)
    if isinstance(info_dict, dict) and info_dict:
        return info_dict
    info_list = getattr(instance, "info_list", None)
    if isinstance(info_list, list) and info_list:
        return info_list
    return {}


class Research_Enrichment_Skiptracer(IntelModuleBase):
    """Aggregate Skiptracer enrichment data into profile['enrichment']."""

    MODULE_NAME = "Research_Enrichment_Skiptracer"

    def __init__(
        self,
        identifier: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        schema_payload = _load_profile_schema()
        input_schema = _build_input_schema(schema_payload)
        output_schema = _build_output_schema(schema_payload)
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=input_schema,
            output_schema=output_schema,
            logger=logger,
        )
        self.identifier = identifier

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        identifiers = self._collect_identifiers(profile)
        if not identifiers:
            raise ValueError("No valid identifiers found for Skiptracer enrichment.")

        self._last_result = {"input": {"identifiers": identifiers}}
        self.log_result()

        skiptracer_available = _ensure_skiptracer_on_path()
        if not skiptracer_available:
            self.logger.warning("Skiptracer repo not available; returning empty enrichment payload.")

        raw_results: List[Dict[str, Any]] = []
        sources: List[Dict[str, Any]] = []
        accounts: List[Dict[str, Any]] = []
        locations: List[Dict[str, Any]] = []
        associations: List[Dict[str, Any]] = []
        correlations: List[Dict[str, Any]] = []
        breach_count = 0
        timestamps: List[datetime] = []

        if skiptracer_available:
            _prepare_skiptracer_globals()

        for identifier in identifiers:
            plugin_payloads: List[Dict[str, Any]] = []
            if skiptracer_available:
                plugin_payloads = self._run_plugins(identifier)

            if not plugin_payloads:
                raw_results.append(
                    {
                        "identifier": identifier["normalized"],
                        "type": identifier["type"],
                        "payload": {},
                    }
                )
                continue

            for plugin_payload in plugin_payloads:
                payload = plugin_payload.get("payload") or {}
                raw_results.append(
                    {
                        "identifier": identifier["normalized"],
                        "type": identifier["type"],
                        "payload": {
                            "plugin": plugin_payload.get("plugin"),
                            "category": plugin_payload.get("category"),
                            "data": payload,
                        },
                    }
                )
                summary = self._summarize_payload(
                    identifier,
                    payload,
                    plugin_payload.get("plugin") or "Skiptracer",
                    plugin_payload.get("category") or "unknown",
                )
                sources.extend(summary["sources"])
                accounts.extend(summary["signals"]["accounts"])
                locations.extend(summary["signals"]["locations"])
                associations.extend(summary["signals"]["associations"])
                correlations.extend(summary["correlations"])
                breach_count += summary["breaches"]
                timestamps.extend(summary["timestamps"])

        scores = self._score_profile(accounts, locations, associations, breach_count, timestamps)

        enrichment = {
            "identifiers": identifiers,
            "sources": self._dedupe_sources(sources),
            "signals": {
                "accounts": self._dedupe_signals(accounts, "url"),
                "locations": self._dedupe_signals(locations, "label"),
                "associations": self._dedupe_signals(associations, "name"),
            },
            "correlations": self._dedupe_correlations(correlations),
            "scores": scores,
            "metadata": {
                "tool": "Skiptracer",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            },
            "raw_results": raw_results,
        }
        return {"enrichment": enrichment}

    def _collect_identifiers(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates: List[str] = []
        if self.identifier:
            candidates.append(self.identifier)
        contact = profile.get("contact", {}) if isinstance(profile, dict) else {}
        candidates.extend(contact.get("emails") or [])
        candidates.extend(contact.get("phones") or [])
        candidates.extend(contact.get("usernames") or [])

        normalized: List[Dict[str, Any]] = []
        seen = set()
        for value in candidates:
            if not value:
                continue
            ident_type, cleaned, valid = _infer_identifier(str(value))
            if not cleaned:
                continue
            key = (ident_type, cleaned)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "type": ident_type,
                    "value": str(value).strip(),
                    "normalized": cleaned,
                    "valid": valid,
                }
            )
        return normalized

    def _run_plugins(self, identifier: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for spec in _PLUGIN_SPECS:
            if identifier["type"] not in spec["types"]:
                continue
            plugin_class = _load_plugin_class(spec["module"], spec["class"])
            if not plugin_class:
                self.logger.debug("Skiptracer plugin not available: %s", spec["name"])
                continue
            try:
                instance = plugin_class()
            except Exception as exc:
                self.logger.warning("Skiptracer plugin init failed (%s): %s", spec["name"], exc)
                continue
            try:
                if spec["arg_order"] == "type_value":
                    output = instance.get_info(identifier["type"], identifier["normalized"])
                else:
                    output = instance.get_info(identifier["normalized"], identifier["type"])
            except Exception as exc:
                self.logger.warning("Skiptracer plugin failed (%s): %s", spec["name"], exc)
                continue

            payload = _collect_plugin_payload(instance, output)
            results.append(
                {
                    "plugin": spec["name"],
                    "category": spec["category"],
                    "payload": payload if isinstance(payload, (dict, list)) else {},
                }
            )
        return results

    def _summarize_payload(
        self,
        identifier: Dict[str, Any],
        payload: Any,
        plugin_name: str,
        category: str,
    ) -> Dict[str, Any]:
        sources: List[Dict[str, Any]] = []
        accounts: List[Dict[str, Any]] = []
        locations: List[Dict[str, Any]] = []
        associations: List[Dict[str, Any]] = []
        correlations: List[Dict[str, Any]] = []

        result_count = self._count_records(payload)
        confidence = _CATEGORY_CONFIDENCE.get(category, _CATEGORY_CONFIDENCE["unknown"])
        if result_count:
            sources.append(
                {
                    "name": plugin_name,
                    "category": category,
                    "results": int(result_count),
                    "confidence": confidence,
                }
            )
            correlations.append(
                {
                    "identifier": identifier["normalized"],
                    "source": category,
                    "field": "signals",
                    "confidence": confidence,
                }
            )

        accounts.extend(self._extract_accounts(payload))
        locations.extend(self._extract_locations(payload))
        associations.extend(self._extract_associations(payload))
        timestamps = _extract_timestamp(payload)

        breach_count = result_count if category == "breach" else 0

        return {
            "sources": sources,
            "signals": {
                "accounts": accounts,
                "locations": locations,
                "associations": associations,
            },
            "correlations": correlations,
            "breaches": breach_count,
            "timestamps": timestamps,
        }

    def _count_records(self, records: Any) -> int:
        if records is None:
            return 0
        if isinstance(records, list):
            return len(records)
        if isinstance(records, dict):
            if "results" in records and isinstance(records["results"], list):
                return len(records["results"])
            return len(records)
        return 1

    def _extract_accounts(self, payload: Any) -> List[Dict[str, Any]]:
        accounts: List[Dict[str, Any]] = []
        for node in _walk_payload(payload):
            platform = node.get("platform") or node.get("site") or node.get("service")
            handle = node.get("username") or node.get("handle") or node.get("user")
            url = node.get("url") or node.get("profile") or ""
            if platform or handle or url:
                confidence = self._confidence_from_source(node, 0.5)
                accounts.append(
                    {
                        "platform": str(platform or "unknown"),
                        "handle": str(handle or ""),
                        "url": str(url or ""),
                        "source": str(node.get("source") or "skiptracer"),
                        "confidence": confidence,
                    }
                )
        return accounts

    def _extract_locations(self, payload: Any) -> List[Dict[str, Any]]:
        locations: List[Dict[str, Any]] = []
        for node in _walk_payload(payload):
            city = node.get("city") or ""
            state = node.get("state") or node.get("region") or ""
            country = node.get("country") or ""
            label = node.get("location") or node.get("address") or ""
            if city or state or country or label:
                confidence = self._confidence_from_source(node, 0.45)
                locations.append(
                    {
                        "label": str(label or ""),
                        "city": str(city or ""),
                        "state": str(state or ""),
                        "country": str(country or ""),
                        "source": str(node.get("source") or "skiptracer"),
                        "confidence": confidence,
                    }
                )
        return locations

    def _extract_associations(self, payload: Any) -> List[Dict[str, Any]]:
        associations: List[Dict[str, Any]] = []
        for node in _walk_payload(payload):
            name = node.get("name") or node.get("entity") or node.get("company")
            relationship = node.get("relationship") or node.get("relation") or node.get("role")
            if name or relationship:
                confidence = self._confidence_from_source(node, 0.4)
                associations.append(
                    {
                        "name": str(name or ""),
                        "relationship": str(relationship or "associated"),
                        "source": str(node.get("source") or "skiptracer"),
                        "confidence": confidence,
                    }
                )
        return associations

    def _confidence_from_source(self, node: Dict[str, Any], base: float) -> float:
        source = str(node.get("source") or "").lower()
        if "social" in source:
            boost = 0.25
        elif "public" in source:
            boost = 0.2
        elif "breach" in source or "leak" in source:
            boost = 0.15
        else:
            boost = 0.05
        return min(1.0, base + boost)

    def _score_profile(
        self,
        accounts: Sequence[Dict[str, Any]],
        locations: Sequence[Dict[str, Any]],
        associations: Sequence[Dict[str, Any]],
        breach_count: int,
        timestamps: Sequence[datetime],
    ) -> Dict[str, float]:
        completeness = 0.0
        if accounts:
            completeness += 40.0
        if locations:
            completeness += 30.0
        if associations:
            completeness += 30.0

        freshness = 0.0
        if timestamps:
            newest = max(timestamps)
            age_days = max(0.0, (datetime.now(timezone.utc) - newest).total_seconds() / 86400)
            if age_days <= 30:
                freshness = 90.0
            elif age_days <= 180:
                freshness = 65.0
            elif age_days <= 365:
                freshness = 45.0
            else:
                freshness = 25.0

        risk = min(100.0, breach_count * 12.0)
        if breach_count and risk < 25.0:
            risk = 25.0

        return {
            "completeness": round(completeness, 2),
            "freshness": round(freshness, 2),
            "risk": round(risk, 2),
        }

    def _dedupe_sources(self, entries: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = {}
        for entry in entries:
            key = (entry["name"], entry["category"])
            existing = seen.get(key)
            if not existing:
                seen[key] = dict(entry)
                continue
            existing["results"] = max(existing["results"], entry["results"])
            existing["confidence"] = max(existing["confidence"], entry["confidence"])
        return list(seen.values())

    def _dedupe_signals(self, entries: Sequence[Dict[str, Any]], key_field: str) -> List[Dict[str, Any]]:
        seen = {}
        for entry in entries:
            key = str(entry.get(key_field) or "").lower()
            if not key:
                key = json.dumps(entry, sort_keys=True)
            if key not in seen:
                seen[key] = dict(entry)
                continue
            if entry.get("confidence", 0) > seen[key].get("confidence", 0):
                seen[key] = dict(entry)
        return list(seen.values())

    def _dedupe_correlations(self, entries: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for entry in entries:
            key = (entry["identifier"], entry["source"], entry["field"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped
