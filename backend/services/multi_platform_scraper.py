"""
Multi-Platform Social Scraper — Reddit, X/Twitter, LinkedIn, Facebook
Scraping method: Public HTML / JSON endpoints only. No API keys required.

Platforms:
  - Reddit:   reddit.com/search.json  (public, no auth)
  - X:        nitter (open-source Twitter proxy) HTML scraping
  - LinkedIn: DuckDuckGo HTML search with site filter (HTML scraping)
  - Facebook: DuckDuckGo HTML search with site filter (HTML scraping)

All keyword queries are enriched with sales-intent phrases aligned to the
5 signal types the Gemini scorer understands:
  product_request, competitor_pain, active_evaluation, advice_seeking, urgent_need
"""

import httpx
import asyncio
import re
import hashlib
from typing import List, Dict, Any, Optional
import os
from urllib.parse import urlparse, parse_qs, unquote

# ── Sales-intent keyword booster phrases ──────────────────────────────────────
# These are appended to user keywords to bias search results toward buying signals.
INTENT_PHRASES = [
    "looking for",
    "need recommendation",
    "best alternative",
    "anyone using",
    "switching from",
    "too expensive",
    "replacing",
    "recommend a tool",
    "what CRM",
    "what software",
    "urgent need",
]

COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ─────────────────────────────────────────────────────────────────────────────
# REDDIT  (public .json endpoint — already working)
# ─────────────────────────────────────────────────────────────────────────────
class RedditScraper:
    BASE_URL = "https://www.reddit.com/search.json"

    STOPWORDS = {
        "a", "an", "the", "for", "to", "of", "and", "or", "in", "on", "with",
        "best", "need", "looking", "recommend", "recommendation", "software",
        "tool", "tools", "platform", "solution", "solutions",
    }

    def _keyword_tokens(self, keyword: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9]+", (keyword or "").lower())
        filtered = [t for t in tokens if t not in self.STOPWORDS and len(t) > 1]
        return filtered or [t for t in tokens if len(t) > 1]

    def _build_query(self, keyword: str) -> str:
        tokens = self._keyword_tokens(keyword)
        return " ".join(tokens[:4]) if tokens else keyword

    def _matches_keywords(self, text: str, keywords: List[str]) -> List[str]:
        normalized = re.sub(r"\s+", " ", (text or "").lower()).strip()
        matched: List[str] = []
        for kw in keywords:
            kw_norm = re.sub(r"\s+", " ", (kw or "").lower()).strip()
            if not kw_norm:
                continue
            tokens = self._keyword_tokens(kw_norm)
            if not tokens:
                continue
            hits = sum(1 for t in tokens if t in normalized)
            min_hits = 1 if len(tokens) == 1 else 2 if len(tokens) <= 3 else max(2, len(tokens) - 1)
            if hits >= min_hits:
                matched.append(kw)
        return matched

    async def _fetch_keyword(self, client: httpx.AsyncClient, keyword: str, all_kws: List[str], limit: int) -> List[Dict]:
        params = {"q": self._build_query(keyword), "sort": "new", "limit": limit}
        try:
            r = await client.get(self.BASE_URL, params=params, timeout=10,
                                 headers={"User-Agent": "SocialPipe/1.0"})
            if r.status_code == 429:
                return []
            r.raise_for_status()
            posts = r.json().get("data", {}).get("children", [])
            results = []
            for post in posts:
                d = post.get("data", {})
                title, body = d.get("title", ""), d.get("selftext", "")
                matched = self._matches_keywords(f"{title} {body}", all_kws)
                if not matched:
                    continue
                results.append({
                    "id":               d.get("id"),
                    "title":            title,
                    "body":             body,
                    "subreddit":        d.get("subreddit"),
                    "author":           d.get("author"),
                    "url":              f"https://reddit.com{d.get('permalink')}",
                    "created_utc":      d.get("created_utc"),
                    "platform":         "Reddit",
                    "matched_keywords": matched,
                })
            return results
        except Exception as e:
            print(f"[Reddit] Error for '{keyword}': {e}")
            return []

    async def fetch_posts(self, keywords: List[str], limit: int = 15) -> List[Dict]:
        async with httpx.AsyncClient() as client:
            batches = await asyncio.gather(
                *[self._fetch_keyword(client, kw, keywords, limit) for kw in keywords],
                return_exceptions=True
            )
        seen, results = set(), []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                if item and item.get("id") and item["id"] not in seen:
                    seen.add(item["id"])
                    results.append(item)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# X / TWITTER  (Nitter — open-source Twitter front-end, no API key)
# Falls back through multiple public Nitter instances.
# ─────────────────────────────────────────────────────────────────────────────
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.fdn.fr",
    "https://nitter.1d4.us",
    "https://nitter.nl",
]

class TwitterScraper:
    def _keyword_tokens(self, keyword: str) -> List[str]:
        tokens = re.findall(r"[a-z0-9]+", (keyword or "").lower())
        stopwords = {"a", "an", "the", "for", "to", "of", "and", "or", "in", "on", "with", "best", "need", "looking", "recommend"}
        filtered = [t for t in tokens if t not in stopwords and len(t) > 1]
        return filtered or [t for t in tokens if len(t) > 1]

    def _build_query(self, keyword: str) -> str:
        """Build a sales-intent enriched query for better signal quality."""
        base = " ".join(self._keyword_tokens(keyword)[:4]) or keyword
        return f"{base} (looking OR need OR recommend OR alternative OR switching OR replacing OR expensive)"

    def _parse_nitter_html(self, html: str, keyword: str, base_url: str) -> List[Dict]:
        results = []
        # Find tweet blocks in Nitter HTML
        tweet_blocks = re.findall(
            r'<div class="tweet-body">(.*?)</div>\s*</div>\s*</div>',
            html, re.DOTALL
        )
        # Simpler: extract permalinks and tweet text
        permalinks = re.findall(r'href="(/[^/]+/status/\d+)"', html)
        texts = re.findall(
            r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )

        for i, (permalink, raw_text) in enumerate(zip(permalinks, texts)):
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", "", raw_text).strip()
            text = re.sub(r"\s+", " ", text)
            if len(text) < 20:
                continue

            # Extract username from permalink  /username/status/id
            parts = permalink.strip("/").split("/")
            username = parts[0] if parts else "unknown"
            tweet_id = parts[2] if len(parts) > 2 else str(i)
            post_id  = f"x_{tweet_id}"
            url      = f"https://x.com{permalink}"

            results.append({
                "id":               post_id,
                "title":            text[:140],
                "body":             text,
                "subreddit":        None,
                "author":           f"@{username}",
                "url":              url,
                "created_utc":      None,
                "platform":         "X",
                "matched_keywords": [keyword],
            })
            if len(results) >= 8:
                break
        return results

    async def _search_nitter(self, client: httpx.AsyncClient, keyword: str) -> List[Dict]:
        query = self._build_query(keyword)
        for instance in NITTER_INSTANCES:
            try:
                url = f"{instance}/search"
                params = {"q": query, "f": "tweets"}
                r = await client.get(url, params=params, timeout=10, headers=COMMON_HEADERS)
                if r.status_code == 200 and "tweet" in r.text.lower():
                    results = self._parse_nitter_html(r.text, keyword, instance)
                    if results:
                        return results
            except Exception as e:
                print(f"[X/Nitter] Instance {instance} failed: {e}")
                continue
        print(f"[X] All Nitter instances failed for '{keyword}'")
        return []

    async def fetch_posts(self, keywords: List[str], limit: int = 8) -> List[Dict]:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
            batches = await asyncio.gather(
                *[self._search_nitter(client, kw) for kw in keywords],
                return_exceptions=True
            )
        seen, results = set(), []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                if item and item.get("id") and item["id"] not in seen:
                    seen.add(item["id"])
                    results.append(item)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE SITE-SEARCH SCRAPER  (base for LinkedIn and Facebook)
# Searches Google for site:platform.com {keyword} — no API key needed.
# ─────────────────────────────────────────────────────────────────────────────
class GoogleSiteScraper:
    PLATFORM: str = "Unknown"
    SITE:     str = ""

    def _build_query(self, keyword: str) -> str:
        """Enrich keyword with sales-intent terms for better results."""
        tokens = re.findall(r"[a-z0-9]+", (keyword or "").lower())
        stopwords = {"a", "an", "the", "for", "to", "of", "and", "or", "in", "on", "with", "best", "need", "looking", "recommend"}
        filtered = [t for t in tokens if t not in stopwords and len(t) > 1]
        base = " ".join((filtered or tokens)[:5]) or keyword
        return f"site:{self.SITE} {base} (looking OR recommend OR alternative OR switching OR need)"

    def _stable_id(self, url: str) -> str:
        return f"{self.PLATFORM.lower()}_{hashlib.md5(url.encode()).hexdigest()[:12]}"

    def _parse_google_results(self, html: str, keyword: str) -> List[Dict]:
        results = []

        # Extract organic result blocks — Google wraps results in <div class="g">
        # We look for title + URL + snippet patterns
        blocks = re.findall(r'<div class="g">(.*?)</div></div></div>', html, re.DOTALL)

        if not blocks:
            # Fallback: find all hrefs + snippets
            links   = re.findall(r'<a href="(https://[^"]+)"', html)
            snippets = re.findall(r'<span[^>]*>([^<]{60,300})</span>', html)
            for link, snippet in zip(links[:10], snippets[:10]):
                if self.SITE not in link:
                    continue
                results.append(self._make_item(link, link, snippet, keyword))
            return results

        for block in blocks[:10]:
            # Extract URL
            link_match = re.search(r'href="(https://[^"]+)"', block)
            if not link_match:
                continue
            link = link_match.group(1)
            if self.SITE not in link:
                continue

            # Extract title
            title_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.DOTALL)
            title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""

            # Extract snippet
            snip_match = re.search(r'<div[^>]*data-sncf[^>]*>(.*?)</div>', block, re.DOTALL)
            if not snip_match:
                snip_match = re.search(r'<span[^>]*>([^<]{40,})</span>', block, re.DOTALL)
            snippet = re.sub(r"<[^>]+>", "", snip_match.group(1)).strip() if snip_match else ""

            if not snippet and not title:
                continue
            results.append(self._make_item(link, title, snippet, keyword))

        return results

    def _make_item(self, url: str, title: str, body: str, keyword: str) -> Dict:
        # Best-effort author from URL path
        try:
            path_parts = url.split("//")[-1].split("/")
            # linkedin.com/in/name or /posts/name, facebook.com/username
            slug = next((p for p in path_parts[1:] if p and p not in ("posts", "in", "pub")), "unknown")
            author = slug.replace("-", " ").replace(".", " ").title()[:40]
        except Exception:
            author = "Unknown"

        return {
            "id":               self._stable_id(url),
            "title":            title[:200],
            "body":             body[:500],
            "subreddit":        None,
            "author":           author,
            "url":              url,
            "created_utc":      None,
            "platform":         self.PLATFORM,
            "matched_keywords": [keyword],
        }

    async def _search_keyword(self, client: httpx.AsyncClient, keyword: str, num: int = 8) -> List[Dict]:
        query = self._build_query(keyword)
        params = {
            "q":   query,
            "num": num,
            "hl":  "en",
            "gl":  "us",
        }
        try:
            r = await client.get(
                "https://www.google.com/search",
                params=params,
                timeout=12,
                headers={
                    **COMMON_HEADERS,
                    "Accept": "text/html,application/xhtml+xml",
                }
            )
            if r.status_code in (429, 403):
                print(f"[{self.PLATFORM}] Google rate-limited for '{keyword}'. Skipping.")
                return []
            return self._parse_google_results(r.text, keyword)
        except Exception as e:
            print(f"[{self.PLATFORM}] Google search error for '{keyword}': {e}")
            return []

    async def fetch_posts(self, keywords: List[str], limit: int = 8) -> List[Dict]:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            batches = await asyncio.gather(
                *[self._search_keyword(client, kw, limit) for kw in keywords],
                return_exceptions=True
            )
        seen, results = set(), []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                if item and item.get("id") and item["id"] not in seen:
                    seen.add(item["id"])
                    results.append(item)
        return results


class DuckDuckGoSiteScraper(GoogleSiteScraper):
    async def _search_keyword(self, client: httpx.AsyncClient, keyword: str, num: int = 8) -> List[Dict]:
        query = self._build_query(keyword)
        params = {"q": query}
        try:
            r = await client.get(
                "https://duckduckgo.com/html/",
                params=params,
                timeout=12,
                headers={
                    **COMMON_HEADERS,
                    "Accept": "text/html,application/xhtml+xml",
                }
            )
            if r.status_code in (429, 403):
                print(f"[{self.PLATFORM}] DuckDuckGo rate-limited for '{keyword}'. Skipping.")
                return []
            return self._parse_ddg_results(r.text, keyword)[:num]
        except Exception as e:
            print(f"[{self.PLATFORM}] DuckDuckGo search error for '{keyword}': {e}")
            return []

    def _parse_ddg_results(self, html: str, keyword: str) -> List[Dict]:
        results: List[Dict] = []
        blocks = re.findall(r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
        if not blocks:
            blocks = re.findall(r'<div class="results">([\s\S]*?)</div>\s*</body>', html, re.DOTALL)
            blocks = blocks[:1] if blocks else []

        for block in blocks:
            links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>', block, re.DOTALL)

            for idx, (href, raw_title) in enumerate(links[:12]):
                url = self._decode_ddg_url(href)
                if not url or self.SITE not in url:
                    continue

                title = re.sub(r"<[^>]+>", "", raw_title).strip()
                snippet_raw = ""
                if idx < len(snippets):
                    snippet_raw = snippets[idx][0] or snippets[idx][1] or ""
                snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()
                if not title and not snippet:
                    continue

                results.append(self._make_item(url, title, snippet, keyword))

        return results

    def _decode_ddg_url(self, href: str) -> str:
        if not href:
            return ""
        h = href.strip()
        if h.startswith("//"):
            h = f"https:{h}"
        if h.startswith("https://duckduckgo.com/l/") or h.startswith("http://duckduckgo.com/l/"):
            try:
                parsed = urlparse(h)
                qs = parse_qs(parsed.query)
                uddg = (qs.get("uddg") or [""])[0]
                return unquote(uddg) if uddg else ""
            except Exception:
                return ""
        return h


class LinkedInScraper(DuckDuckGoSiteScraper):
    PLATFORM = "LinkedIn"
    SITE     = "linkedin.com/posts"


class FacebookScraper(DuckDuckGoSiteScraper):
    PLATFORM = "Facebook"
    SITE     = "facebook.com"

    def _build_query(self, keyword: str) -> str:
        # Facebook public group posts are better surfaced this way
        tokens = re.findall(r"[a-z0-9]+", (keyword or "").lower())
        stopwords = {"a", "an", "the", "for", "to", "of", "and", "or", "in", "on", "with", "best", "need", "looking", "recommend"}
        filtered = [t for t in tokens if t not in stopwords and len(t) > 1]
        base = " ".join((filtered or tokens)[:5]) or keyword
        return f"site:facebook.com/groups {base} (looking OR recommend OR alternative OR need)"


# ─────────────────────────────────────────────────────────────────────────────
# MULTI-PLATFORM ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
class MultiPlatformScraper:
    def __init__(self):
        self.reddit   = RedditScraper()
        self.twitter  = TwitterScraper()
        self.linkedin = LinkedInScraper()
        self.facebook = FacebookScraper()

    async def fetch_all(self, keywords: List[str], limit_per_platform: int = 8, platforms: Optional[List[str]] = None) -> List[Dict]:
        """
        Run all 4 platform scrapers concurrently.
        Returns merged, deduplicated list sorted by platform.
        """
        selected = {p.lower() for p in (platforms or ["reddit", "x", "linkedin", "facebook"])}
        print(f"[MultiScraper] Scanning {len(keywords)} keyword(s) across: {', '.join(sorted(selected))}")

        jobs = []
        labels = []
        if "reddit" in selected:
            jobs.append(self.reddit.fetch_posts(keywords, limit=limit_per_platform))
            labels.append("Reddit")
        if "x" in selected or "twitter" in selected:
            jobs.append(self.twitter.fetch_posts(keywords, limit=limit_per_platform))
            labels.append("X")
        if "linkedin" in selected:
            jobs.append(self.linkedin.fetch_posts(keywords, limit=limit_per_platform))
            labels.append("LinkedIn")
        if "facebook" in selected or "fb" in selected:
            jobs.append(self.facebook.fetch_posts(keywords, limit=limit_per_platform))
            labels.append("Facebook")

        if not jobs:
            return []

        results_by_platform = await asyncio.gather(*jobs, return_exceptions=True)

        seen: set = set()
        all_posts: List[Dict] = []
        for label, batch in zip(labels, results_by_platform):
            if isinstance(batch, Exception):
                print(f"[{label}] Scraper error: {batch}")
                continue
            count = 0
            for item in batch:
                if item and item.get("id") and item["id"] not in seen:
                    seen.add(item["id"])
                    all_posts.append(item)
                    count += 1
            print(f"[{label}] {count} posts collected")

        print(f"[MultiScraper] Total: {len(all_posts)} unique posts")
        return all_posts


multi_scraper = MultiPlatformScraper()
