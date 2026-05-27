import httpx
import asyncio
from typing import List, Dict, Any
import re

class RedditScraper:
    def __init__(self):
        self.base_url = "https://www.reddit.com/search.json"
        self.headers = {"User-Agent": "SocialPipe/1.0"}

    def _matches_keywords(self, text: str, keywords: List[str]) -> List[str]:
        normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
        matched: List[str] = []
        for kw in keywords:
            kw_norm = re.sub(r"\s+", " ", (kw or "").lower()).strip()
            if not kw_norm:
                continue
            tokens = [t for t in re.split(r"\s+", kw_norm) if t]
            if tokens and all(t in normalized for t in tokens):
                matched.append(kw)
        return matched

    async def _fetch_keyword(self, client: httpx.AsyncClient, keyword: str, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Fetch Reddit posts for a single keyword (async, non-blocking)."""
        params = {"q": keyword, "sort": "new", "limit": limit}
        try:
            print(f"Searching Reddit for: '{keyword}'...")
            response = await client.get(self.base_url, params=params, timeout=10)

            if response.status_code == 429:
                print(f"Rate limited for '{keyword}'. Skipping.")
                return []

            response.raise_for_status()
            data = response.json()
            posts = data.get("data", {}).get("children", [])

            results = []
            for post in posts:
                post_data = post.get("data", {})
                title = post_data.get("title") or ""
                body  = post_data.get("selftext") or ""
                matched_keywords = self._matches_keywords(f"{title} {body}", keywords)
                if not matched_keywords:
                    continue

                results.append({
                    "id":               post_data.get("id"),
                    "title":            title,
                    "body":             body,
                    "subreddit":        post_data.get("subreddit"),
                    "author":           post_data.get("author"),
                    "url":              f"https://reddit.com{post_data.get('permalink')}",
                    "created_utc":      post_data.get("created_utc"),
                    "platform":         "Reddit",
                    "matched_keywords": matched_keywords,
                })
            return results

        except httpx.RequestError as e:
            print(f"Error fetching keyword '{keyword}': {e}")
            return []
        except Exception as e:
            print(f"Unexpected error for '{keyword}': {e}")
            return []

    async def fetch_posts(self, keywords: List[str], limit: int = 25) -> List[Dict[str, Any]]:
        """
        Concurrently search Reddit for all keywords using async HTTP (non-blocking).
        """
        async with httpx.AsyncClient(headers=self.headers) as client:
            # Fire all keyword searches in parallel
            tasks = [self._fetch_keyword(client, kw, keywords, limit) for kw in keywords]
            results = await asyncio.gather(*tasks)

        # Flatten + deduplicate by post id
        seen: set = set()
        all_leads: List[Dict[str, Any]] = []
        for batch in results:
            for lead in batch:
                if lead["id"] not in seen:
                    seen.add(lead["id"])
                    all_leads.append(lead)

        return all_leads


reddit_scraper = RedditScraper()


async def main():
    """
    Test function for RedditScraper
    """
    import json
    test_keywords = ["need voice AI", "looking for CRM", "sales call software"]

    print("--- Starting Reddit Scraper Test ---")
    results = await reddit_scraper.fetch_posts(test_keywords, limit=5)

    print(f"\nFound {len(results)} potential leads.")
    for i, lead in enumerate(results[:3], 1):
        print(f"\nLead #{i}:")
        print(f"Title: {lead['title'][:70]}...")
        print(f"Author: u/{lead['author']}")
        print(f"Subreddit: r/{lead['subreddit']}")
        print(f"URL: {lead['url']}")

if __name__ == "__main__":
    asyncio.run(main())
