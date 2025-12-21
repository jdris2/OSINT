"""
Research_Social_Twitter_Intelligence

Data Source:
  - Twint (https://github.com/twintproject/twint), a Twitter scraper that does
    not require the Twitter API or authentication.

Purpose:
  - Analyze social behavior from tweets, searches, and network metadata, and
    normalize results into profile["social"].
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from intel_engine.core.module_base import IntelModuleBase

_TWITTER_HOSTS = ("twitter.com", "www.twitter.com", "x.com", "www.x.com")
_HANDLE_PATTERN = re.compile(r"@?([A-Za-z0-9_]{1,15})")

_POSITIVE_WORDS = {
    "good",
    "great",
    "love",
    "excellent",
    "awesome",
    "happy",
    "fortunate",
    "positive",
    "success",
    "win",
}
_NEGATIVE_WORDS = {
    "bad",
    "terrible",
    "hate",
    "awful",
    "sad",
    "angry",
    "negative",
    "fail",
    "loss",
    "worse",
}


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


def _build_schemas(schema_payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    contact_schema = schema_payload.get("properties", {}).get("contact")
    social_schema = schema_payload.get("properties", {}).get("social")
    if not social_schema:
        raise ValueError("profile_schema.json does not define a social section.")
    input_schema = {
        "type": "object",
        "properties": {
            **({"contact": contact_schema} if contact_schema else {}),
            **({"social": social_schema} if social_schema else {}),
        },
    }
    output_schema = {
        "type": "object",
        "required": ["social"],
        "properties": {"social": social_schema},
    }
    return input_schema, output_schema


def _extract_username(profile: Dict[str, Any]) -> Optional[str]:
    contact = profile.get("contact", {}) if isinstance(profile, dict) else {}
    for entry in contact.get("usernames", []) or []:
        handle = _normalize_handle(str(entry))
        if handle:
            return handle

    social = profile.get("social", {}) if isinstance(profile, dict) else {}
    for link in social.get("profile_links", []) or []:
        handle = _handle_from_url(str(link))
        if handle:
            return handle
    return None


def _normalize_handle(value: str) -> Optional[str]:
    if not value:
        return None
    match = _HANDLE_PATTERN.fullmatch(value.strip())
    return match.group(1) if match else None


def _handle_from_url(value: str) -> Optional[str]:
    if not value:
        return None
    lowered = value.lower()
    if not any(host in lowered for host in _TWITTER_HOSTS):
        return None
    try:
        path = value.split("://", 1)[-1].split("/", 1)[1]
    except IndexError:
        return None
    handle = path.split("/", 1)[0]
    return _normalize_handle(handle)


def _extract_keywords(profile: Dict[str, Any]) -> List[str]:
    keywords = os.environ.get("TWINT_KEYWORDS", "").strip()
    if keywords:
        return [kw.strip() for kw in keywords.split(",") if kw.strip()]
    social = profile.get("social", {}) if isinstance(profile, dict) else {}
    for entry in social.get("last_activity", []) or []:
        summary = entry.get("summary", "") if isinstance(entry, dict) else ""
        if "keywords=" in summary:
            value = summary.split("keywords=", 1)[-1].split(" ", 1)[0]
            return [kw.strip() for kw in value.split(",") if kw.strip()]
    return []


def _extract_date_range() -> Tuple[Optional[str], Optional[str]]:
    since = os.environ.get("TWINT_SINCE", "").strip() or None
    until = os.environ.get("TWINT_UNTIL", "").strip() or None
    return since, until


def _parse_tweet_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def _sentiment_score(texts: Iterable[str]) -> float:
    score = 0
    for text in texts:
        tokens = re.findall(r"[A-Za-z']+", text.lower())
        for token in tokens:
            if token in _POSITIVE_WORDS:
                score += 1
            elif token in _NEGATIVE_WORDS:
                score -= 1
    return score


def _sentiment_label(score: float) -> str:
    if score > 2:
        return "positive"
    if score < -2:
        return "negative"
    return "neutral"


def _extract_follow_handles(follow_df, kind: str) -> List[str]:
    if follow_df is None:
        return []
    try:
        records = follow_df.to_dict(orient="records")
    except Exception:
        return []
    handles: List[str] = []
    for record in records:
        data = record.get(kind)
        if isinstance(data, dict):
            for _, values in data.items():
                if isinstance(values, list):
                    handles.extend(values)
        elif isinstance(data, list):
            handles.extend(data)
    return [handle for handle in handles if isinstance(handle, str)]


class Research_Social_Twitter_Intelligence(IntelModuleBase):
    MODULE_NAME = "Research_Social_Twitter_Intelligence"

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        schema_payload = _load_profile_schema()
        input_schema, output_schema = _build_schemas(schema_payload)
        super().__init__(
            module_name=self.MODULE_NAME,
            profile_schema=input_schema,
            output_schema=output_schema,
            logger=logger,
        )

    def _execute_impl(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        username = _extract_username(profile)
        if not username:
            raise ValueError(
                "No Twitter username provided in profile.contact.usernames or "
                "profile.social.profile_links."
            )

        keywords = _extract_keywords(profile)
        since, until = _extract_date_range()
        limit = int(os.environ.get("TWINT_LIMIT", "200"))
        lang = os.environ.get("TWINT_LANG", "").strip() or None

        self._last_result = {
            "source": "Twint",
            "input": {
                "username": username,
                "keywords": keywords,
                "since": since,
                "until": until,
                "limit": limit,
                "lang": lang,
            },
        }
        self.log_result()

        tweets = self._collect_tweets(username, keywords, since, until, limit, lang)
        followers, following, user_links = self._collect_network(username, limit)

        social = self._prepare_social_section(profile)
        social["platforms"] = sorted(set(social.get("platforms", []) + ["Twitter"]))

        profile_links = list(social.get("profile_links") or [])
        profile_links.extend(user_links)
        for tweet in tweets:
            link = tweet.get("link")
            if isinstance(link, str) and link.startswith("http"):
                profile_links.append(link)
        profile_links = self._merge_unique([], profile_links)[:20]

        last_activity = list(social.get("last_activity") or [])
        last_activity.extend(
            self._build_activity_entries(
                username=username,
                tweets=tweets,
                followers=followers,
                following=following,
                keywords=keywords,
                since=since,
                until=until,
            )
        )

        social["profile_links"] = profile_links
        social["last_activity"] = last_activity
        result = {"social": social}
        self._last_result = {"source": "Twint", "result": result}
        self.log_result()
        return result

    def _collect_tweets(
        self,
        username: str,
        keywords: List[str],
        since: Optional[str],
        until: Optional[str],
        limit: int,
        lang: Optional[str],
    ) -> List[Dict[str, Any]]:
        try:
            import twint
            from twint.storage import panda as panda_storage
        except ImportError as exc:
            raise RuntimeError(
                "Twint is required. Install with `pip install twint` or use the cloned "
                "repository."
            ) from exc

        panda_storage.clean()

        config = twint.Config()
        config.Username = username
        config.Limit = limit
        config.Pandas = True
        config.Hide_output = True
        config.Since = since
        config.Until = until
        config.Lang = lang
        config.Pandas_clean = False

        twint.run.Profile(config)
        combined: List[Dict[str, Any]] = []
        tweets_df = panda_storage.Tweets_df
        if tweets_df is not None:
            combined.extend(tweets_df.to_dict(orient="records"))

        if keywords:
            panda_storage.clean()
            config = twint.Config()
            config.Username = username
            config.Search = " ".join(keywords)
            config.Limit = limit
            config.Pandas = True
            config.Hide_output = True
            config.Since = since
            config.Until = until
            config.Lang = lang
            config.Pandas_clean = False
            twint.run.Search(config)

            search_df = panda_storage.Tweets_df
            if search_df is not None:
                combined.extend(search_df.to_dict(orient="records"))

        seen = set()
        deduped: List[Dict[str, Any]] = []
        for tweet in combined:
            tweet_id = str(tweet.get("id") or "")
            if not tweet_id or tweet_id in seen:
                continue
            seen.add(tweet_id)
            deduped.append(tweet)
        return deduped

    def _collect_network(self, username: str, limit: int) -> Tuple[int, int, List[str]]:
        try:
            import twint
            from twint.storage import panda as panda_storage
        except ImportError as exc:
            raise RuntimeError(
                "Twint is required. Install with `pip install twint` or use the cloned "
                "repository."
            ) from exc

        followers = 0
        following = 0
        links: List[str] = [f"https://twitter.com/{username}"]

        panda_storage.clean()
        config = twint.Config()
        config.Username = username
        config.User_full = True
        config.Pandas = True
        config.Hide_output = True
        config.Pandas_clean = False
        twint.run.Lookup(config)

        user_df = panda_storage.User_df
        if user_df is not None and not user_df.empty:
            record = user_df.iloc[0].to_dict()
            followers = int(record.get("followers") or 0)
            following = int(record.get("following") or 0)
            if record.get("url"):
                links.append(str(record["url"]))

        follow_limit = min(limit, 200)
        try:
            panda_storage.clean()
            config = twint.Config()
            config.Username = username
            config.Limit = follow_limit
            config.Pandas = True
            config.Hide_output = True
            config.Pandas_clean = False
            twint.run.Followers(config)
            followers_df = panda_storage.Follow_df

            panda_storage.clean()
            config = twint.Config()
            config.Username = username
            config.Limit = follow_limit
            config.Pandas = True
            config.Hide_output = True
            config.Pandas_clean = False
            twint.run.Following(config)
            following_df = panda_storage.Follow_df

            follower_handles = _extract_follow_handles(followers_df, "followers")
            following_handles = _extract_follow_handles(following_df, "following")
            if follower_handles and not followers:
                followers = len(set(follower_handles))
            if following_handles and not following:
                following = len(set(following_handles))

            for handle in follower_handles[:5] + following_handles[:5]:
                handle = _normalize_handle(handle)
                if handle:
                    links.append(f"https://twitter.com/{handle}")
        except Exception:
            pass

        return followers, following, links

    def _build_activity_entries(
        self,
        username: str,
        tweets: List[Dict[str, Any]],
        followers: int,
        following: int,
        keywords: List[str],
        since: Optional[str],
        until: Optional[str],
    ) -> List[Dict[str, str]]:
        now = datetime.now(timezone.utc).isoformat()

        tweet_texts = [tweet.get("tweet", "") for tweet in tweets if tweet.get("tweet")]
        timestamps = [_parse_tweet_timestamp(tweet.get("created_at")) for tweet in tweets]
        timestamps = [ts for ts in timestamps if ts]

        first_ts = min(timestamps).date().isoformat() if timestamps else "unknown"
        last_ts = max(timestamps).date().isoformat() if timestamps else "unknown"

        days_span = (
            (max(timestamps) - min(timestamps)).days + 1
            if len(timestamps) > 1
            else 1
        )
        tweet_count = len(tweets)
        avg_per_day = round(tweet_count / days_span, 2) if days_span else 0.0

        likes = sum(int(tweet.get("nlikes") or 0) for tweet in tweets)
        retweets = sum(int(tweet.get("nretweets") or 0) for tweet in tweets)
        replies = sum(int(tweet.get("nreplies") or 0) for tweet in tweets)
        reach = likes + retweets + replies

        hashtag_counts = Counter()
        mention_counts = Counter()
        for tweet in tweets:
            hashtags = tweet.get("hashtags") or []
            for tag in hashtags:
                hashtag_counts[tag.lower()] += 1
            for handle in re.findall(r"@([A-Za-z0-9_]{1,15})", tweet.get("tweet", "")):
                mention_counts[handle.lower()] += 1

        top_hashtags = [f"#{tag}" for tag, _ in hashtag_counts.most_common(5)]
        top_mentions = [f"@{handle}" for handle, _ in mention_counts.most_common(5)]

        sentiment_score = _sentiment_score(tweet_texts)
        sentiment_label = _sentiment_label(sentiment_score)

        keyword_text = ",".join(keywords) if keywords else "none"
        date_range = f"{since or first_ts}..{until or last_ts}"

        summary = (
            "Timeline: tweets={tweets}, range={range}, avg_per_day={avg}, "
            "reach={reach}, sentiment={sentiment} (score {score}), "
            "top_hashtags={hashtags}, top_mentions={mentions}, "
            "followers={followers}, following={following}, keywords={keywords}"
        ).format(
            tweets=tweet_count,
            range=date_range,
            avg=avg_per_day,
            reach=reach,
            sentiment=sentiment_label,
            score=sentiment_score,
            hashtags="|".join(top_hashtags) or "none",
            mentions="|".join(top_mentions) or "none",
            followers=followers,
            following=following,
            keywords=keyword_text,
        )

        return [
            {
                "platform": "Twitter",
                "timestamp": now,
                "summary": summary,
            }
        ]

    def _prepare_social_section(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        source = profile.get("social", {}) if isinstance(profile, dict) else {}
        social: Dict[str, Any] = {
            "platforms": list(source.get("platforms") or []),
            "profile_links": list(source.get("profile_links") or []),
            "last_activity": [
                entry for entry in list(source.get("last_activity") or []) if isinstance(entry, dict)
            ],
        }
        return social

    def _merge_unique(self, existing: Iterable[str], incoming: Iterable[str]) -> List[str]:
        merged: List[str] = list(existing)
        seen = set(merged)
        for entry in incoming:
            if entry not in seen:
                merged.append(entry)
                seen.add(entry)
        return merged


class ResearchSocialTwitterIntelligence(Research_Social_Twitter_Intelligence):
    """Backwards-compatible alias for module discovery."""
