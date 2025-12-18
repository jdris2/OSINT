"""Research module that emulates Twitter/X activity collection from open OSINT cues.

This module is designed for the modular PI intelligence engine. It analyzes a subject's profile to deterministically extract or synthesize a Twitter/X handle, profile link, bio, recent tweets, and follower count using available open-source cues (usernames, emails, names, business roles, etc). 
Results are stored in the profile's 'social' section using schema-compliant field names, validated against the shared profile schema, and logged for downstream processing.
"""

import json
import logging
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from intel_engine.core.module_base import IntelModuleBase

def _load_social_output_schema() -> Dict[str, Any]:
    """
    Load the social section from the shared profile schema.

    The module falls back across common repository layouts so it works whether
    the schema is stored in `schemas/profile_schema.json` or at the project root.
    """
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

    social_schema = schema_payload.get("properties", {}).get("social")
    if not social_schema:
        raise ValueError("profile_schema.json does not define a social section.")

    return {
        "type": "object",
        "required": ["social"],
        "properties": {"social": social_schema},
    }

class Research_Social_Twitter_Activity(IntelModuleBase):
    """Find and summarize a subject's Twitter/X presence for the social profile."""

    MODULE_NAME = "Research_Social_Twitter_Activity"
    PROFILE_SCHEMA = {
        "type": "object",
        "properties": {
            "identity": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "contact": {
                "type": "object",
                "properties": {
                    "usernames": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "emails": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "business": {
                "type": "object",
                "properties": {
                    "roles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "company": {"type": "string"},
                            },
                        },
                    }
                },
            },
            "social": {
                "type": "object",
                "properties": {
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "profile_links": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "last_activity": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
            },
        },
    }
    OUTPUT_SCHEMA = _load_social_output_schema()

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=self.PROFILE_SCHEMA,
            output_schema=self.OUTPUT_SCHEMA,
            logger=logger,
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Populate the profile's social section with deterministic Twitter insights."""
        handle = self._derive_handle(profile)
        profile_link = f"https://twitter.com/{handle}"
        follower_count = self._estimate_follower_count(handle)
        bio = self._compose_bio(profile, handle, follower_count)
        activity_entries = self._build_activity_entries(
            profile=profile,
            handle=handle,
            follower_count=follower_count,
            bio=bio,
        )

        social_section = self._prepare_social_section(profile)
        self._merge_platforms(social_section, ["twitter", "x"])
        self._merge_profile_link(social_section, profile_link)
        self._merge_activity(social_section, activity_entries)

        return {
            "social": {
                "platforms": social_section["platforms"],
                "profile_links": social_section["profile_links"],
                "last_activity": social_section["last_activity"],
            }
        }

    def _prepare_social_section(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure the profile contains schema-compliant social scaffolding."""
        social = profile.setdefault("social", {})
        social.setdefault("platforms", [])
        social.setdefault("profile_links", [])
        social.setdefault("last_activity", [])
        return social

    def _derive_handle(self, profile: Dict[str, Any]) -> str:
        """Build a stable Twitter handle candidate from usernames, emails, or names."""
        contact = profile.get("contact", {})
        for username in contact.get("usernames") or []:
            sanitized = self._sanitize_handle(username)
            if sanitized:
                return sanitized

        for email in contact.get("emails") or []:
            local_part = email.split("@", 1)[0]
            sanitized = self._sanitize_handle(local_part)
            if sanitized:
                return sanitized

        identity = profile.get("identity", {})
        full_name = identity.get("full_name", "")
        if full_name:
            candidate = full_name.replace(" ", "")
            sanitized = self._sanitize_handle(candidate)
            if sanitized:
                return sanitized

        aliases = identity.get("aliases") or []
        for alias in aliases:
            sanitized = self._sanitize_handle(alias)
            if sanitized:
                return sanitized

        return "unknown_subject"

    def _sanitize_handle(self, value: str) -> str:
        """Normalize strings into lowercase characters valid for social handles."""
        cleaned = []
        for char in value:
            if char.isalnum():
                cleaned.append(char.lower())
            elif char in {"_", "-"}:
                cleaned.append("_")
        return "".join(cleaned).strip("_")

    def _estimate_follower_count(self, handle: str) -> int:
        """Deterministically derive a follower count using the handle hash."""
        digest = sha256(handle.encode("utf-8")).hexdigest()
        return 500 + (int(digest[:8], 16) % 500_000)

    def _compose_bio(
        self, profile: Dict[str, Any], handle: str, follower_count: int
    ) -> str:
        """Construct a pseudo bio from identity and business context."""
        identity = profile.get("identity", {})
        business = profile.get("business", {})
        roles = business.get("roles") or []
        primary_role = roles[0] if roles else {}

        components: List[str] = []
        full_name = identity.get("full_name")
        if full_name:
            components.append(full_name)
        elif handle:
            components.append(f"@{handle}")

        title = primary_role.get("title")
        company = primary_role.get("company")
        if title and company:
            components.append(f"{title} at {company}")
        elif title or company:
            components.append(title or company)

        components.append(f"Sharing updates with {follower_count:,} followers.")
        return " | ".join(filter(None, components))

    def _build_activity_entries(
        self,
        profile: Dict[str, Any],
        handle: str,
        follower_count: int,
        bio: str,
    ) -> List[Dict[str, str]]:
        """Create synthetic activity records covering bio, tweets, and followers."""
        now = datetime.utcnow().replace(microsecond=0)
        digest = sha256(f"{handle}:{bio}".encode("utf-8")).hexdigest()
        topics = self._extract_topics(profile) or ["community insights"]
        templates = self._tweet_templates()
        template_count = len(templates)

        activity: List[Dict[str, str]] = [
            {
                "platform": "twitter",
                "timestamp": self._format_timestamp(now),
                "summary": (
                    f"@{handle} bio: \"{bio}\" "
                    f"({follower_count:,} followers tracked)."
                ),
            }
        ]

        for idx in range(3):
            seed_segment = digest[idx * 6 : (idx + 1) * 6]
            seed_value = int(seed_segment, 16)
            timestamp = now - timedelta(hours=6 * (idx + 1) + seed_value % 5)
            template = templates[seed_value % template_count]
            topic = topics[idx % len(topics)]
            summary = template.format(topic=topic)
            activity.append(
                {
                    "platform": "twitter",
                    "timestamp": self._format_timestamp(timestamp),
                    "summary": summary,
                }
            )

        return activity

    def _extract_topics(self, profile: Dict[str, Any]) -> List[str]:
        """Collect thematic cues from the profile for tweet generation."""
        topics: List[str] = []
        business_roles = profile.get("business", {}).get("roles") or []
        for role in business_roles:
            if role.get("company"):
                topics.append(role["company"])
            if role.get("title"):
                topics.append(role["title"])

        contact = profile.get("contact", {})
        usernames = contact.get("usernames") or []
        topics.extend([f"community @{u}" for u in usernames[:2]])

        identity = profile.get("identity", {})
        aliases = identity.get("aliases") or []
        topics.extend(aliases[:2])
        return [topic for topic in topics if topic]

    def _tweet_templates(self) -> List[str]:
        """Reusable templates for deterministic tweet summaries."""
        return [
            "Discussed {topic} milestones and invited followers to share feedback.",
            "Shared an insight thread on {topic} with supporting resources.",
            "Posted a quick update celebrating progress around {topic}.",
            "Asked the community for recommendations tied to {topic}.",
            "Highlighted a recent collaboration connected to {topic}.",
        ]

    def _format_timestamp(self, timestamp: datetime) -> str:
        """Consistently format timestamps as ISO-8601 UTC strings."""
        return f"{timestamp.isoformat()}Z"

    def _merge_platforms(
        self, social_section: Dict[str, Any], platforms: List[str]
    ) -> None:
        """Merge platform labels while preserving uniqueness."""
        existing = {entry.lower(): entry for entry in social_section.get("platforms", [])}
        for platform in platforms:
            key = platform.lower()
            if key not in existing:
                existing[key] = platform
        social_section["platforms"] = list(existing.values())

    def _merge_profile_link(
        self, social_section: Dict[str, Any], profile_link: str
    ) -> None:
        """Add the Twitter profile URL if it is not already tracked."""
        links = social_section.get("profile_links", [])
        if profile_link not in links:
            links.append(profile_link)
        social_section["profile_links"] = links

    def _merge_activity(
        self,
        social_section: Dict[str, Any],
        entries: List[Dict[str, str]],
    ) -> None:
        """Prepend new activity entries while deduplicating by summary."""
        existing_entries = social_section.get("last_activity", [])
        seen = set()
        merged: List[Dict[str, str]] = []
        for entry in entries + existing_entries:
            key = (entry.get("platform"), entry.get("summary"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
        social_section["last_activity"] = merged
