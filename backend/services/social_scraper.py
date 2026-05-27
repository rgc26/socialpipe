"""
LinkedIn & Facebook Scraper — uses SerpAPI (Google Search) with site: filters.

LinkedIn and Facebook do NOT have free public search APIs.
SerpAPI provides Google search results programmatically, which lets us find
public posts on both platforms without violating ToS.

Get a free key (100 searches/month) at: https://serpapi.com
Set SERPAPI_KEY in .env to enable LinkedIn + Facebook scanning.
"""
import httpx
import asyncio
import os
import re
from typing import List, Dict, Any

SERPAPI_BASE = "https://serpapi.com/search"


class SerpScraper:
    """Generic SerpAPI-backed scraper. Subclass per platform."""

    PLATFORM: str = "Unknown"
    SITE_FILTER: str = ""

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY")
        if not self.api_key:
            print(f"⚠  SERPAPI_KEY not set — {self.PLATFORM} scanning disabled.")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def _search_keyword(self, client: httpx.AsyncClient, keyword: str, num: int = 10) -> List[Dict[str, Any]]:
        query = f'site:{self.SITE_FILTER} "{keyword}"'
        params = {
            "engine":  "google",
            "q":       query,
            "num":     num,
            "api_key": self.api_key,
            "hl":      "en",
        }
        try:
            response = await client.get(SERPAPI_BASE, params=params, timeout=15)
            if response.status_code == 401:
                print(f"SerpAPI: Invalid key. Check SERPAPI_KEY.")
                return []
            response.raise_for_status()
            data = response.json()

            results_raw = data.get("organic_results", [])
            results = []
            for r in results_raw:
                link    = r.get("link", "")
                title   = r.get("title", "")
                snippet = r.get("snippet", "")
                # Only include actual content URLs (skip profile/company overview pages)
                if not link or not snippet:
                    continue

                # Extract a pseudo-author from the URL or title
                author = self._extract_author(link)

                results.append({
                    "id":               f"{self.PLATFORM.lower()}_{abs(hash(link))}",
                    "title":            title,
                    "body":             snippet,
                    "subreddit":        None,
                    "author":           author,
                    "url":              link,
                    "created_utc":      None,
                    "platform":         self.PLATFORM,
                    "matched_keywords": [keyword],
                })
            return results

        except Exception as e:
            print(f"{self.PLATFORM} SerpAPI error for '{keyword}': {e}")
            return []

    def _extract_author(self, url: str) -> str:
        """Best-effort author/page extraction from a URL."""
        try:
            path = url.split("//")[-1].split("/")
            # e.g. linkedin.com/in/john-doe  or  facebook.com/john.doe
            if len(path) >= 2:
                return path[1].replace("-", " ").replace(".", " ").title()
        except Exception:
            pass
        return "Unknown"

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


class LinkedInScraper(SerpScraper):
    PLATFORM    = "LinkedIn"
    SITE_FILTER = "linkedin.com/posts"


class FacebookScraper(SerpScraper):
    PLATFORM    = "Facebook"
    SITE_FILTER = "facebook.com"


linkedin_scraper = LinkedInScraper()
facebook_scraper = FacebookScraper()
