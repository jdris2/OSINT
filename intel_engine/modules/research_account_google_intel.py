"""
Research_Account_Google_Intel

Data Source:
  - GHunt (https://github.com/mxrch/GHunt), which uses Google People and Maps
    APIs to enumerate public Google account metadata.

Purpose:
  - Investigates a Google account by email, correlates signals across YouTube,
    Maps, and Photos, and stores normalized results under profile["digital"].
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from intel_engine.core.module_base import IntelModuleBase


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
    raise FileNotFoundError("Unable to locate schemas/profile_schema.json.")


def _build_output_schema(schema_payload: Dict[str, Any]) -> Dict[str, Any]:
    digital_schema = schema_payload.get("properties", {}).get("digital")
    if not digital_schema:
        raise ValueError("profile_schema.json does not define a digital section.")
    return {
        "type": "object",
        "required": ["digital"],
        "properties": {"digital": digital_schema},
    }


def _resolve_ghunt_root(ghunt_root: Optional[Path]) -> Optional[Path]:
    if ghunt_root:
        return Path(ghunt_root).expanduser()
    candidate = Path(__file__).resolve().parents[2] / "GHunt"
    return candidate if candidate.exists() else None


def _ensure_ghunt_importable(ghunt_root: Optional[Path]) -> None:
    if not ghunt_root:
        return
    resolved = str(ghunt_root)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _extract_email(profile: Dict[str, Any], override: Optional[str]) -> str:
    if override and override.strip():
        return override.strip().lower()
    contact = profile.get("contact", {}) if isinstance(profile, dict) else {}
    emails = contact.get("emails") or []
    for email in emails:
        if isinstance(email, str) and email.strip():
            return email.strip().lower()
    raise ValueError("No email address provided in profile.contact.emails.")


def _format_timestamp(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


async def _run_ghunt_lookup(email: str, ghunt_root: Optional[Path]) -> Dict[str, Any]:
    _ensure_ghunt_importable(ghunt_root)
    try:
        from ghunt.helpers.utils import get_httpx_client
        from ghunt.helpers import auth, gmaps
        from ghunt.apis.peoplepa import PeoplePaHttp
    except ImportError as exc:
        raise RuntimeError(
            "GHunt is required. Install with `pip install ghunt` or use the "
            "cloned repository in editable mode."
        ) from exc

    as_client = get_httpx_client()
    try:
        ghunt_creds = await auth.load_and_auth(as_client)
        people_pa = PeoplePaHttp(ghunt_creds)
        is_found, target = await people_pa.people_lookup(
            as_client, email, params_template="max_details"
        )
        if not is_found:
            return {"found": False}

        container = "PROFILE"
        if container not in target.sourceIds:
            container = next(iter(target.sourceIds.keys()), None)

        profile_photo_url = None
        cover_photo_url = None
        apps: List[str] = []
        last_updated = None

        if container:
            if container in target.profilePhotos:
                photo = target.profilePhotos[container]
                if photo and not photo.isDefault and photo.url:
                    profile_photo_url = photo.url
            if container in target.coverPhotos:
                cover = target.coverPhotos[container]
                if cover and not cover.isDefault and cover.url:
                    cover_photo_url = cover.url
            if container in target.sourceIds:
                last_updated = target.sourceIds[container].lastUpdated
            if container in target.inAppReachability:
                apps = list(target.inAppReachability[container].apps or [])

        maps_status = "skipped"
        maps_stats: Dict[str, int] = {}
        maps_reviews: List[Any] = []
        maps_photos: List[Any] = []
        if target.personId:
            try:
                maps_status, maps_stats, maps_reviews, maps_photos = await gmaps.get_reviews(
                    as_client, target.personId
                )
            except Exception:
                maps_status = "error"

        return {
            "found": True,
            "person_id": target.personId,
            "container": container,
            "apps": apps,
            "last_updated": last_updated,
            "profile_photo_url": profile_photo_url,
            "cover_photo_url": cover_photo_url,
            "maps_status": maps_status,
            "maps_stats": maps_stats,
            "maps_reviews": maps_reviews,
            "maps_photos": maps_photos,
        }
    finally:
        await as_client.aclose()


def _run_async(coro: Any) -> Any:
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class Research_Account_Google_Intel(IntelModuleBase):
    """Investigate Google account metadata using GHunt."""

    MODULE_NAME = "Research_Account_Google_Intel"

    def __init__(
        self,
        email: Optional[str] = None,
        ghunt_root: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        schema_payload = _load_profile_schema()
        output_schema = _build_output_schema(schema_payload)
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=schema_payload,
            output_schema=output_schema,
            logger=logger,
        )
        self.email = email
        self.ghunt_root = _resolve_ghunt_root(ghunt_root)

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        email = _extract_email(profile, self.email)
        self._last_result = {"source": "GHunt", "input": {"email": email}}
        self.log_result()

        ghunt_data = _run_async(_run_ghunt_lookup(email, self.ghunt_root))
        digital = self._prepare_digital_section(profile)

        if not ghunt_data.get("found"):
            profile["digital"] = digital
            return {"digital": digital}

        last_seen = _format_timestamp(ghunt_data.get("last_updated"))
        apps = ghunt_data.get("apps") or []
        apps_lower = {app.lower() for app in apps if isinstance(app, str)}

        devices = list(digital.get("devices") or [])
        domains = list(digital.get("domains") or [])

        if ghunt_data.get("person_id"):
            devices.append(
                {
                    "type": "google_account",
                    "os": "google",
                    "identifier": f"gaia:{ghunt_data['person_id']};email:{email}",
                    "last_seen": last_seen,
                }
            )

        services: Dict[str, float] = {}
        if any("youtube" in app for app in apps_lower):
            services["youtube"] = 0.7
            domains.append("youtube.com")

        maps_status = ghunt_data.get("maps_status")
        maps_reviews = ghunt_data.get("maps_reviews") or []
        maps_photos = ghunt_data.get("maps_photos") or []
        if maps_status in ("", "empty", "private"):
            if maps_reviews or maps_photos:
                services["maps"] = 0.9
            elif maps_status == "private":
                services["maps"] = 0.5
            else:
                services["maps"] = 0.6
            domains.append("maps.google.com")

        photos_present = bool(
            ghunt_data.get("profile_photo_url")
            or ghunt_data.get("cover_photo_url")
            or maps_photos
        )
        if photos_present:
            services["photos"] = 0.8 if ghunt_data.get("profile_photo_url") else 0.6
            domains.append("photos.google.com")

        maps_stats = ghunt_data.get("maps_stats") or {}
        for service, confidence in services.items():
            extra = ""
            if service == "maps" and maps_stats:
                extra = f";reviews={maps_stats.get('reviews', 0)};photos={maps_stats.get('photos', 0)}"
            devices.append(
                {
                    "type": "google_service",
                    "os": "google",
                    "identifier": f"service:{service};confidence={confidence:.2f}{extra}",
                    "last_seen": last_seen,
                }
            )

        if len(services) >= 2:
            avg_confidence = sum(services.values()) / len(services)
            service_list = ",".join(sorted(services.keys()))
            devices.append(
                {
                    "type": "google_service_correlation",
                    "os": "google",
                    "identifier": (
                        f"services={service_list};confidence={avg_confidence:.2f}"
                    ),
                    "last_seen": last_seen,
                }
            )

        digital["domains"] = self._merge_unique(digital.get("domains") or [], domains)
        digital["devices"] = devices

        profile["digital"] = digital
        return {"digital": digital}

    def _prepare_digital_section(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        source = profile.get("digital", {}) if isinstance(profile, dict) else {}
        digital: Dict[str, Any] = {
            "ips": list(source.get("ips") or []),
            "domains": list(source.get("domains") or []),
            "devices": [
                entry for entry in list(source.get("devices") or []) if isinstance(entry, dict)
            ],
            "exposed_ports": [
                entry for entry in list(source.get("exposed_ports") or []) if isinstance(entry, dict)
            ],
        }
        return digital

    def _merge_unique(self, existing: Iterable[str], incoming: Iterable[str]) -> List[str]:
        merged: List[str] = list(existing)
        seen = set(merged)
        for entry in incoming:
            if entry not in seen:
                merged.append(entry)
                seen.add(entry)
        return merged


class ResearchAccountGoogleIntel(Research_Account_Google_Intel):
    """Backwards-compatible alias for module discovery."""
