"""
Research_Automation_SpiderFoot

Data Source:
  - SpiderFoot (https://github.com/smicallef/spiderfoot), an open-source OSINT
    automation framework that aggregates hundreds of data sources for full-spectrum
    reconnaissance and entity discovery.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from intel_engine.core.module_base import IntelModuleBase

_SCAN_PROFILE_DEFAULT = "standard"
_SCAN_PROFILES = {
    "light": {"usecase": "passive", "maxthreads": 2, "fetchtimeout": 4},
    "standard": {"usecase": "footprint", "maxthreads": 4, "fetchtimeout": 6},
    "deep": {"usecase": "all", "maxthreads": 8, "fetchtimeout": 10},
}
_USECASE_KEYS = {"all", "passive", "footprint", "investigate"}
_ENTITY_TYPES = ("emails", "domains", "ips")
_MAX_RELATIONSHIPS = 1500
_MAX_RAW_EVENTS = 1500


def _load_profile_schema() -> Dict[str, Any]:
    candidate_paths = [
        Path(__file__).resolve().parents[1] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "schemas" / "profile_schema.json",
        Path(__file__).resolve().parents[2] / "profile_schema.json",
    ]
    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    raise FileNotFoundError(
        "Unable to locate schemas/profile_schema.json for validation."
    )


def _build_input_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    contact_schema = schema_payload.get("properties", {}).get("contact")
    digital_schema = schema_payload.get("properties", {}).get("digital")
    identity_schema = schema_payload.get("properties", {}).get("identity")
    return {
        "type": "object",
        "properties": {
            "contact": contact_schema or {},
            "digital": digital_schema or {},
            "identity": identity_schema or {},
        },
    }


def _build_output_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    intelligence_schema = schema_payload.get("properties", {}).get("intelligence")
    if intelligence_schema:
        return {
            "type": "object",
            "required": ["intelligence"],
            "properties": {"intelligence": intelligence_schema},
        }
    return {
        "type": "object",
        "required": ["intelligence"],
        "properties": {
            "intelligence": {
                "type": "object",
                "required": ["spiderfoot"],
                "properties": {
                    "spiderfoot": {
                        "type": "object",
                        "required": [
                            "targets",
                            "scan_profile",
                            "modules_requested",
                            "modules_enabled",
                            "entities",
                            "relationships",
                            "graph",
                            "summary",
                            "execution",
                            "errors",
                        ],
                        "properties": {
                            "targets": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["type", "value"],
                                    "properties": {
                                        "type": {"type": "string"},
                                        "value": {"type": "string"},
                                    },
                                },
                            },
                            "scan_profile": {"type": "string"},
                            "modules_requested": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "modules_enabled": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "entities": {
                                "type": "object",
                                "required": list(_ENTITY_TYPES),
                                "properties": {
                                    "emails": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "domains": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "ips": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                            },
                            "entity_confidence": {
                                "type": "object",
                                "properties": {
                                    "emails": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["value", "confidence"],
                                            "properties": {
                                                "value": {"type": "string"},
                                                "confidence": {"type": "number"},
                                            },
                                        },
                                    },
                                    "domains": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["value", "confidence"],
                                            "properties": {
                                                "value": {"type": "string"},
                                                "confidence": {"type": "number"},
                                            },
                                        },
                                    },
                                    "ips": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["value", "confidence"],
                                            "properties": {
                                                "value": {"type": "string"},
                                                "confidence": {"type": "number"},
                                            },
                                        },
                                    },
                                },
                            },
                            "relationships": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": [
                                        "source",
                                        "target",
                                        "event_type",
                                        "confidence",
                                    ],
                                    "properties": {
                                        "source": {"type": "string"},
                                        "target": {"type": "string"},
                                        "event_type": {"type": "string"},
                                        "confidence": {"type": "number"},
                                        "module": {"type": "string"},
                                    },
                                },
                            },
                            "graph": {
                                "type": "object",
                                "required": ["nodes", "edges"],
                                "properties": {
                                    "nodes": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "type", "label"],
                                            "properties": {
                                                "id": {"type": "string"},
                                                "type": {"type": "string"},
                                                "label": {"type": "string"},
                                            },
                                        },
                                    },
                                    "edges": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": [
                                                "source",
                                                "target",
                                                "event_type",
                                                "confidence",
                                            ],
                                            "properties": {
                                                "source": {"type": "string"},
                                                "target": {"type": "string"},
                                                "event_type": {"type": "string"},
                                                "confidence": {"type": "number"},
                                            },
                                        },
                                    },
                                },
                            },
                            "summary": {
                                "type": "object",
                                "required": ["event_counts", "entity_counts"],
                                "properties": {
                                    "event_counts": {
                                        "type": "object",
                                        "additionalProperties": {"type": "integer"},
                                    },
                                    "entity_counts": {
                                        "type": "object",
                                        "required": list(_ENTITY_TYPES),
                                        "properties": {
                                            "emails": {"type": "integer"},
                                            "domains": {"type": "integer"},
                                            "ips": {"type": "integer"},
                                        },
                                    },
                                },
                            },
                            "execution": {
                                "type": "object",
                                "required": ["duration_s", "scan_ids"],
                                "properties": {
                                    "duration_s": {"type": "number"},
                                    "scan_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                            },
                            "errors": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["target", "error"],
                                    "properties": {
                                        "target": {"type": "string"},
                                        "error": {"type": "string"},
                                    },
                                },
                            },
                            "raw_events": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["data", "type", "module"],
                                    "properties": {
                                        "data": {"type": "string"},
                                        "type": {"type": "string"},
                                        "module": {"type": "string"},
                                        "confidence": {"type": "number"},
                                    },
                                },
                            },
                        },
                    }
                },
            }
        },
    }


def _normalize_scan_profile(value: Optional[str]) -> str:
    if not value:
        return _SCAN_PROFILE_DEFAULT
    cleaned = value.strip().lower()
    if cleaned not in _SCAN_PROFILES:
        raise ValueError(
            f"scan_profile must be one of {sorted(_SCAN_PROFILES.keys())}."
        )
    return cleaned


def _normalize_module_selection(
    module_selection: Optional[Iterable[Any]],
) -> List[str]:
    if not module_selection:
        return []
    if isinstance(module_selection, str):
        parts = [chunk.strip() for chunk in module_selection.split(",")]
        return [part for part in parts if part]
    return [str(item).strip() for item in module_selection if str(item).strip()]


def _normalize_email(value: str) -> Optional[str]:
    cleaned = value.strip().lower()
    return cleaned if "@" in cleaned else None


def _normalize_domain(value: str) -> Optional[str]:
    cleaned = value.strip().lower().strip(".")
    return cleaned if "." in cleaned else None


def _normalize_ip(value: str) -> Optional[str]:
    cleaned = value.strip()
    try:
        return str(ipaddress.ip_address(cleaned))
    except ValueError:
        return None


def _entity_key(value: str, entity_type: str) -> str:
    return f"{entity_type}:{value}"


def _dedupe(values: Iterable[str]) -> List[str]:
    deduped = sorted({value for value in values if value})
    return deduped


def _resolve_spiderfoot_root(spiderfoot_root: Optional[Path]) -> Optional[Path]:
    if spiderfoot_root:
        return Path(spiderfoot_root).expanduser()
    candidate = Path(__file__).resolve().parents[2] / "spiderfoot_repo"
    if candidate.exists():
        return candidate
    return None


def _import_spiderfoot(spiderfoot_root: Optional[Path]) -> None:
    try:
        import sflib  # noqa: F401
        import sfscan  # noqa: F401
        from spiderfoot import SpiderFootHelpers  # noqa: F401
    except ImportError:
        if not spiderfoot_root:
            raise
        sys.path.insert(0, str(spiderfoot_root))
        import sflib  # noqa: F401
        import sfscan  # noqa: F401
        from spiderfoot import SpiderFootHelpers  # noqa: F401


def _load_spiderfoot_modules(spiderfoot_root: Path) -> Dict[str, Any]:
    from spiderfoot import SpiderFootHelpers

    mod_dir = spiderfoot_root / "modules"
    return SpiderFootHelpers.loadModulesAsDict(
        str(mod_dir), ["sfp_template.py"]
    )


def _load_correlation_rules(spiderfoot_root: Path, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    from spiderfoot import SpiderFootDb, SpiderFootCorrelator, SpiderFootHelpers

    correlations_dir = spiderfoot_root / "correlations"
    correlation_raw = SpiderFootHelpers.loadCorrelationRulesRaw(
        f"{str(correlations_dir)}/", ["template.yaml"]
    )
    if not correlation_raw:
        return []
    dbh = SpiderFootDb(config)
    correlator = SpiderFootCorrelator(dbh, correlation_raw)
    rules = correlator.get_ruleset()
    dbh.close()
    return rules


def _build_spiderfoot_config(
    spiderfoot_root: Path, scan_profile: str, max_threads: Optional[int] = None
) -> Dict[str, Any]:
    from spiderfoot import SpiderFootHelpers

    profile_cfg = _SCAN_PROFILES[scan_profile]
    config = {
        "_debug": False,
        "_maxthreads": int(max_threads or profile_cfg["maxthreads"]),
        "__logging": True,
        "__outputfilter": None,
        "_useragent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) "
            "Gecko/20100101 Firefox/102.0"
        ),
        "_dnsserver": "",
        "_fetchtimeout": int(profile_cfg["fetchtimeout"]),
        "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
        "_internettlds_cache": 72,
        "_genericusers": ",".join(
            SpiderFootHelpers.usernamesFromWordlists(["generic-usernames"])
        ),
        "__database": "",
        "__modules__": None,
        "__correlationrules__": None,
        "_socks1type": "",
        "_socks2addr": "",
        "_socks3port": "",
        "_socks4user": "",
        "_socks5pwd": "",
    }
    return config


def _select_modules(
    available: Dict[str, Any],
    scan_profile: str,
    module_selection: Sequence[str],
) -> Tuple[List[str], List[str]]:
    selected = [entry for entry in module_selection if entry]
    if not selected:
        selected = [_SCAN_PROFILES[scan_profile]["usecase"]]

    usecase = None
    explicit_modules: List[str] = []
    for item in selected:
        lowered = item.lower()
        if lowered in _USECASE_KEYS:
            usecase = lowered
            continue
        if item.startswith("sfp_"):
            explicit_modules.append(item)
        else:
            explicit_modules.append(f"sfp_{item}")

    if explicit_modules:
        enabled = [name for name in explicit_modules if name in available]
        return selected, sorted(set(enabled))

    if usecase is None:
        usecase = _SCAN_PROFILES[scan_profile]["usecase"]

    enabled = []
    for name, metadata in available.items():
        groups = metadata.get("group") or []
        if usecase == "all" or usecase in groups:
            enabled.append(name)
    return selected, sorted(set(enabled))


def _target_candidates(profile: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    contact = profile.get("contact", {})
    digital = profile.get("digital", {})
    identity = profile.get("identity", {})
    for username in contact.get("usernames") or []:
        candidates.append(str(username))
    for email in contact.get("emails") or []:
        candidates.append(str(email))
    for domain in digital.get("domains") or []:
        candidates.append(str(domain))
    for ip_value in digital.get("ips") or []:
        candidates.append(str(ip_value))
    for alias in identity.get("aliases") or []:
        candidates.append(str(alias))
    return candidates


def _normalize_target_type(target_type: Optional[str]) -> Optional[str]:
    if not target_type:
        return None
    lowered = target_type.strip().lower()
    mapping = {
        "domain": "INTERNET_NAME",
        "ip": "IP_ADDRESS",
        "ip_address": "IP_ADDRESS",
        "username": "USERNAME",
        "email": "EMAILADDR",
    }
    return mapping.get(lowered, target_type)


def _resolve_targets(
    profile: Dict[str, Any],
    target: Optional[Any],
    target_type: Optional[str],
) -> List[Dict[str, str]]:
    from spiderfoot import SpiderFootHelpers

    normalized_type = _normalize_target_type(target_type)
    targets: List[str] = []
    if target:
        if isinstance(target, (list, tuple, set)):
            targets.extend([str(item) for item in target if str(item).strip()])
        else:
            targets.append(str(target))
    else:
        targets.extend(_target_candidates(profile))

    deduped = []
    for value in targets:
        cleaned = value.strip().strip('"')
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)

    resolved: List[Dict[str, str]] = []
    for value in deduped:
        if normalized_type:
            resolved.append({"type": normalized_type, "value": value})
            continue
        detected = SpiderFootHelpers.targetTypeFromString(value)
        if detected:
            resolved.append({"type": detected, "value": value})
    return resolved


def _confidence_to_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value) / 100.0))
    except (TypeError, ValueError):
        return 0.0


def _normalize_entity_value(value: str) -> Optional[str]:
    email = _normalize_email(value)
    if email:
        return email
    domain = _normalize_domain(value)
    if domain:
        return domain
    ip_value = _normalize_ip(value)
    return ip_value


def _extract_entities(events: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
    emails: List[str] = []
    domains: List[str] = []
    ips: List[str] = []
    for event in events:
        value = event.get("data")
        if not isinstance(value, str):
            continue
        normalized = _normalize_email(value)
        if normalized:
            emails.append(normalized)
            continue
        normalized = _normalize_domain(value)
        if normalized:
            domains.append(normalized)
            continue
        normalized = _normalize_ip(value)
        if normalized:
            ips.append(normalized)
    return {
        "emails": _dedupe(emails),
        "domains": _dedupe(domains),
        "ips": _dedupe(ips),
    }


def _extract_relationships(
    events: Iterable[Dict[str, Any]],
    entity_index: Dict[str, str],
) -> List[Dict[str, Any]]:
    relationships: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for event in events:
        source = event.get("source_data")
        target = event.get("data")
        event_type = event.get("type")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        source_key = entity_index.get(source)
        if not source_key:
            source_key = entity_index.get(_normalize_entity_value(source) or "")
        target_key = entity_index.get(target)
        if not target_key:
            target_key = entity_index.get(_normalize_entity_value(target) or "")
        if not source_key or not target_key:
            continue
        dedupe_key = (source_key, target_key, str(event_type))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        relationships.append(
            {
                "source": source,
                "target": target,
                "event_type": str(event_type),
                "confidence": _confidence_to_score(event.get("confidence")),
                "module": str(event.get("module", "")),
            }
        )
        if len(relationships) >= _MAX_RELATIONSHIPS:
            break
    return relationships


def _build_entity_index(entities: Dict[str, List[str]]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for entity_type, values in entities.items():
        for value in values:
            key = _entity_key(value, entity_type)
            index[value] = key
            normalized = None
            if entity_type == "emails":
                normalized = _normalize_email(value)
            elif entity_type == "domains":
                normalized = _normalize_domain(value)
            elif entity_type == "ips":
                normalized = _normalize_ip(value)
            if normalized:
                index[normalized] = key
    return index


def _build_graph(
    targets: List[Dict[str, str]],
    entities: Dict[str, List[str]],
    relationships: List[Dict[str, Any]],
    entity_index: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    nodes: Dict[str, Dict[str, str]] = {}
    for target in targets:
        key = _entity_key(target["value"], target["type"])
        nodes[key] = {"id": key, "type": target["type"], "label": target["value"]}

    for entity_type, values in entities.items():
        for value in values:
            key = _entity_key(value, entity_type)
            nodes[key] = {"id": key, "type": entity_type, "label": value}

    edges: List[Dict[str, Any]] = []
    for rel in relationships:
        source_key = entity_index.get(rel["source"])
        target_key = entity_index.get(rel["target"])
        if not source_key or not target_key:
            continue
        edges.append(
            {
                "source": source_key,
                "target": target_key,
                "event_type": rel["event_type"],
                "confidence": rel["confidence"],
            }
        )

    return {"nodes": list(nodes.values()), "edges": edges}


def _summarize_events(events: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for event in events:
        event_type = str(event.get("type", "unknown"))
        counts[event_type] = counts.get(event_type, 0) + 1
    return counts


def _calc_entity_confidence(
    events: Iterable[Dict[str, Any]],
    entities: Dict[str, List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    confidence_map: Dict[str, Dict[str, List[float]]] = {
        "emails": {},
        "domains": {},
        "ips": {},
    }
    for event in events:
        data = event.get("data")
        if not isinstance(data, str):
            continue
        score = _confidence_to_score(event.get("confidence"))
        email = _normalize_email(data)
        if email:
            confidence_map["emails"].setdefault(email, []).append(score)
            continue
        domain = _normalize_domain(data)
        if domain:
            confidence_map["domains"].setdefault(domain, []).append(score)
            continue
        ip_value = _normalize_ip(data)
        if ip_value:
            confidence_map["ips"].setdefault(ip_value, []).append(score)

    result: Dict[str, List[Dict[str, Any]]] = {}
    for key in _ENTITY_TYPES:
        entries = []
        for value in entities.get(key, []):
            scores = confidence_map.get(key, {}).get(value, [])
            avg = sum(scores) / len(scores) if scores else 0.0
            entries.append({"value": value, "confidence": round(avg, 3)})
        result[key] = entries
    return result


class Research_Automation_SpiderFoot(IntelModuleBase):
    """Run SpiderFoot OSINT scans and normalize entities into intelligence output."""

    MODULE_NAME = "Research_Automation_SpiderFoot"

    def __init__(
        self,
        target: Optional[Any] = None,
        target_type: Optional[str] = None,
        scan_profile: Optional[str] = None,
        module_selection: Optional[Iterable[Any]] = None,
        spiderfoot_root: Optional[Path] = None,
        max_threads: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        profile_schema = _load_profile_schema()
        input_schema = _build_input_schema(profile_schema)
        output_schema = _build_output_schema(profile_schema)
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=input_schema,
            output_schema=output_schema,
            logger=logger,
        )
        self.target = target
        self.target_type = target_type
        self.scan_profile = _normalize_scan_profile(scan_profile)
        self.module_selection = _normalize_module_selection(module_selection)
        self.spiderfoot_root = _resolve_spiderfoot_root(spiderfoot_root)
        self.max_threads = max_threads

    def validate_input(self) -> None:
        super().validate_input()
        if not self.spiderfoot_root:
            raise FileNotFoundError(
                "SpiderFoot repository not found; clone it or pass spiderfoot_root."
            )
        if not self.spiderfoot_root.exists():
            raise FileNotFoundError(
                f"SpiderFoot repository not found at {self.spiderfoot_root}."
            )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        _import_spiderfoot(self.spiderfoot_root)

        targets = _resolve_targets(profile, self.target, self.target_type)
        if not targets:
            raise ValueError(
                "No valid SpiderFoot targets found. Provide target or profile data."
            )

        self._last_result = {
            "source": "SpiderFoot",
            "input": {
                "targets": targets,
                "scan_profile": self.scan_profile,
                "module_selection": self.module_selection,
            }
        }
        self.log_result()

        env_overrides = {
            "SPIDERFOOT_DATA": "",
            "SPIDERFOOT_CACHE": "",
            "SPIDERFOOT_LOGS": "",
        }
        with tempfile.TemporaryDirectory(prefix="spiderfoot_run_") as temp_root:
            base_path = Path(temp_root)
            for key in env_overrides:
                env_overrides[key] = os.environ.get(key, "")
            os.environ["SPIDERFOOT_DATA"] = str(base_path / "data")
            os.environ["SPIDERFOOT_CACHE"] = str(base_path / "cache")
            os.environ["SPIDERFOOT_LOGS"] = str(base_path / "logs")

            try:
                available_modules = _load_spiderfoot_modules(self.spiderfoot_root)
                requested, enabled = _select_modules(
                    available_modules, self.scan_profile, self.module_selection
                )
                if not enabled:
                    raise ValueError("No SpiderFoot modules enabled for this scan.")

                config_template = _build_spiderfoot_config(
                    self.spiderfoot_root,
                    self.scan_profile,
                    max_threads=self.max_threads,
                )
                config_template["__database"] = str(base_path / "spiderfoot.db")
                config_template["__modules__"] = available_modules
                config_template["__correlationrules__"] = _load_correlation_rules(
                    self.spiderfoot_root, config_template
                )

                started_at = time.time()
                scan_results: List[Dict[str, Any]] = []
                errors: List[Dict[str, str]] = []
                max_workers = min(len(targets), config_template["_maxthreads"])
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(
                            self._run_scan, config_template, enabled, target
                        ): target
                        for target in targets
                    }
                    for future in as_completed(futures):
                        target = futures[future]
                        try:
                            scan_results.append(future.result())
                        except Exception as exc:  # noqa: BLE001
                            message = str(exc)
                            self.logger.error(
                                "SpiderFoot scan failed for %s: %s",
                                target.get("value"),
                                message,
                            )
                            errors.append(
                                {
                                    "target": target.get("value", ""),
                                    "error": message,
                                }
                            )

                duration_s = time.time() - started_at
            finally:
                for key, value in env_overrides.items():
                    if value:
                        os.environ[key] = value
                    else:
                        os.environ.pop(key, None)

        combined_events: List[Dict[str, Any]] = []
        scan_ids: List[str] = []
        for result in scan_results:
            scan_ids.append(result["scan_id"])
            combined_events.extend(result.get("events", []))

        entities = _extract_entities(combined_events)
        entity_index = _build_entity_index(entities)
        for target in targets:
            target_key = _entity_key(target["value"], target["type"])
            entity_index[target["value"]] = target_key
            normalized = _normalize_entity_value(target["value"])
            if normalized:
                entity_index[normalized] = target_key
        relationships = _extract_relationships(combined_events, entity_index)
        graph = _build_graph(targets, entities, relationships, entity_index)
        event_counts = _summarize_events(combined_events)
        entity_confidence = _calc_entity_confidence(combined_events, entities)

        raw_events = [
            {
                "data": str(event.get("data", "")),
                "type": str(event.get("type", "")),
                "module": str(event.get("module", "")),
                "confidence": _confidence_to_score(event.get("confidence")),
            }
            for event in combined_events[:_MAX_RAW_EVENTS]
        ]

        intelligence = {
            "spiderfoot": {
                "targets": targets,
                "scan_profile": self.scan_profile,
                "modules_requested": requested,
                "modules_enabled": enabled,
                "entities": entities,
                "entity_confidence": entity_confidence,
                "relationships": relationships,
                "graph": graph,
                "summary": {
                    "event_counts": event_counts,
                    "entity_counts": {
                        "emails": len(entities["emails"]),
                        "domains": len(entities["domains"]),
                        "ips": len(entities["ips"]),
                    },
                },
                "execution": {"duration_s": round(duration_s, 2), "scan_ids": scan_ids},
                "errors": errors,
                "raw_events": raw_events,
            }
        }

        result = {"intelligence": intelligence}
        self._last_result = {"source": "SpiderFoot", "result": result}
        self.log_result()
        profile["intelligence"] = intelligence
        return result

    def _run_scan(
        self,
        config_template: Dict[str, Any],
        enabled_modules: Sequence[str],
        target: Dict[str, str],
    ) -> Dict[str, Any]:
        from sfscan import SpiderFootScanner
        from spiderfoot import SpiderFootDb, SpiderFootHelpers

        scan_id = SpiderFootHelpers.genScanInstanceId()
        scan_name = f"spiderfoot-{uuid.uuid4().hex[:8]}"
        config = deepcopy(config_template)
        base_db = config_template.get("__database")
        if base_db:
            db_path = Path(base_db).parent
        else:
            db_path = Path(tempfile.gettempdir())
        config["__database"] = str(db_path / f"spiderfoot_{scan_id}.db")

        scanner = SpiderFootScanner(
            scanName=scan_name,
            scanId=scan_id,
            targetValue=target["value"],
            targetType=target["type"],
            moduleList=list(enabled_modules),
            globalOpts=config,
            start=True,
        )

        dbh = SpiderFootDb(config)
        events = dbh.scanResultEvent(scan_id)
        dbh.close()

        sanitized_events: List[Dict[str, Any]] = []
        for event in events:
            sanitized_events.append(
                {
                    "generated": event[0],
                    "data": event[1],
                    "source_data": event[2],
                    "module": event[3],
                    "type": event[4],
                    "confidence": event[5],
                    "visibility": event[6],
                    "risk": event[7],
                }
            )
            if len(sanitized_events) >= _MAX_RAW_EVENTS:
                break

        return {
            "scan_id": scan_id,
            "target": target,
            "events": sanitized_events,
            "status": scanner.status,
        }
