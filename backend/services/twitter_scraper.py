"""
Twitter/X Scraper — uses the official Twitter API v2 (free tier).
Requires: TWITTER_BEARER_TOKEN in .env

Get a free Bearer Token at: https://developer.twitter.com/en/portal/dashboard
Free tier allows recent tweet search (last 7 days), up to 10 results per request.
"""
import httpx
import asyncio
import os
from typing import List, Dict, Any


class TwitterScraper:
    BASE_URL = "https://api.twitter.com/2/tweets/search/recent"

    def __init__(self):
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        if not self.bearer_token:
            print("⚠  TWITTER_BEARER_TOKEN not set — Twitter scanning disabled.")

    @property
    def enabled(self) -> bool:
        return bool(self.bearer_token)

    async def _search_keyword(self, client: httpx.AsyncClient, keyword: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search recent tweets for a single keyword."""
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {
            "query": f"{keyword} -is:retweet lang:en",
            "max_results": max_results,
            "tweet.fields": "id,text,author_id,created_at,entities",
            "expansions": "author_id",
            "user.fields": "username,name",
        }
        try:
            response = await client.get(self.BASE_URL, headers=headers, params=params, timeout=10)
            if response.status_code == 429:
                print(f"Twitter rate limit hit for '{keyword}' — skipping.")
                return []
            if response.status_code == 401:
                print("Twitter: Invalid Bearer Token. Check TWITTER_BEARER_TOKEN.")
                return []
            response.raise_for_status()
            data = response.json()

            tweets   = data.get("data", [])
            users    = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            results  = []

            for tweet in tweets:
                author_id = tweet.get("author_id", "")
                user      = users.get(author_id, {})
                username  = user.get("username", "unknown")

                results.append({
                    "id":          f"tw_{tweet['id']}",
                    "title":       tweet["text"][:120],
                    "body":        tweet["text"],
                    "subreddit":   None,
                    "author":      f"@{username}",
                    "url":         f"https://x.com/{username}/status/{tweet['id']}",
                    "created_utc": tweet.get("created_at"),
                    "platform":    "X",
                    "matched_keywords": [keyword],
                })
            return results

        except Exception as e:
            print(f"Twitter error for '{keyword}': {e}")
            return []

    async def fetch_posts(self, keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        async with httpx.AsyncClient() as client:
            tasks   = [self._search_keyword(client, kw, limit) for kw in keywords]
            batches = await asyncio.gather(*tasks, return_exceptions=True)

        seen: set = set()
        results: List[Dict[str, Any]] = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                if item["id"] not in seen:
                    seen.add(item["id"])
                    results.append(item)
        return results


twitter_scraper = TwitterScraper()
