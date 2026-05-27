from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import os
import asyncio
import re
import httpx
from services.multi_platform_scraper import multi_scraper
from services.gemini_scorer import gemini_scorer
from services.couchbase_client import couchbase_client
from models.lead import Lead

router = APIRouter()

class ScanRequest(BaseModel):
    keywords: List[str]

KEYWORD_STOPWORDS = {
    "need", "looking", "for", "best", "recommend", "recommendation", "help",
    "with", "a", "an", "the", "software", "tool", "tools", "platform",
}

def _keyword_tokens(keyword: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", (keyword or "").lower())
    filtered = [t for t in tokens if t not in KEYWORD_STOPWORDS and len(t) > 1]
    return filtered or [t for t in tokens if len(t) > 1]

def _compact_text(text: str, max_len: int = 420) -> str:
    if not text:
        return ""
    normalized = " ".join(str(text).split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1] + "…"

def _format_post_content(post: dict) -> str:
    platform = str(post.get("platform") or "Social").strip() or "Social"
    title = str(post.get("title") or "").strip()
    body = str(post.get("body") or "").strip()
    subreddit = str(post.get("subreddit") or "").strip()

    if platform.lower() == "reddit" and subreddit:
        heading = f"[r/{subreddit}] {title}".strip()
    else:
        heading = f"[{platform}] {title}".strip()

    return f"{heading}\n\n{body}".strip()

def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("//"):
        return f"https:{u}"
    if u.startswith("www.") or u.startswith("reddit.com") or u.startswith("x.com") or u.startswith("linkedin.com") or u.startswith("facebook.com"):
        return f"https://{u}"
    return u

def _expand_keywords(keywords: List[str]) -> List[str]:
    expanded: List[str] = []
    seen: set = set()

    def add(value: str):
        v = " ".join((value or "").split()).strip().lower()
        if not v or v in seen:
            return
        seen.add(v)
        expanded.append(v)

    for kw in keywords:
        raw = " ".join(str(kw or "").split()).strip()
        if not raw:
            continue
        add(raw)

        tokens = re.findall(r"[a-z0-9]+", raw.lower())
        core_tokens = [t for t in tokens if t not in KEYWORD_STOPWORDS]
        core = " ".join(core_tokens[:4]).strip() or raw.lower()

        add(core)
        add(f"looking for {core}")
        add(f"need {core}")
        add(f"replace {core}")
        add(f"struggling with {core}")
        add(f"{core} too expensive")

    return expanded[:12]

def _looks_like_noise(title: str, body: str) -> bool:
    t = " ".join(str(title or "").split()).lower()
    b = " ".join(str(body or "").split()).lower()
    text = f"{t}\n{b}".strip()
    if not text:
        return True

    noise_phrases = [
        "for hire", "hiring", "job opening", "looking to hire",
        "free services", "free service", "portfolio",
        "i built", "launching", "check out", "my app", "my product",
        "top ", "best ", "list of", "companies", "agency", "development company", "development companies",
        "2026", "guide", "blog", "article",
        "discount", "promo", "limited offer",
        "case study", "how i'm", "how im", "success with", "best practices",
        "tldr:", "here are", "nobody wants to answer",
        "demo", "tutorial", "newsletter", "webinar", "free trial", "my stack",
    ]
    if any(p in text for p in noise_phrases):
        buyer_markers = [
            "i need", "we need", "looking for", "anyone recommend", "recommend",
            "alternatives", "switching from", "replace", "vs", "compare", "?",
            "too expensive", "struggling", "hard to manage", "not working",
        ]
        strong_need = ["we need", "i need", "looking for", "our current", "my current", "too expensive", "not working", "struggling"]
        if not any(m in text for m in buyer_markers) or not any(m in text for m in strong_need):
            return True

    buyer_pronouns = [" i ", " we ", " our ", " my ", " our team "]
    has_buyer_voice = any(p in f" {text} " for p in buyer_pronouns)
    has_ask = ("?" in text) or ("recommend" in text) or ("looking for" in text) or ("any alternatives" in text) or ("what tool" in text) or ("which tool" in text)
    has_intent = any(p in text for p in ["need ", "looking for", "recommend", "alternatives", "switching from", "replace", "vs", "compare"])
    has_pain = any(p in text for p in ["too expensive", "struggling", "problem", "hard to", "not working", "manual", "spreadsheet", "mess"])
    if not ((has_buyer_voice and (has_ask or has_pain)) or (has_intent and has_pain)):
        return True

    return False

def _matches_requested_problem(title: str, body: str, keywords: List[str]) -> bool:
    text = " ".join([str(title or ""), str(body or "")]).lower()
    if not text:
        return False

    pain_or_need = any(
        p in text for p in [
            "need", "looking for", "recommend", "alternative", "replace", "switching",
            "too expensive", "struggling", "problem", "hard to", "not working",
        ]
    )
    buyer_context = any(p in f" {text} " for p in [" i ", " we ", " our ", " my ", " our team ", " my team "])
    ask_context = any(p in text for p in ["?", "recommend", "looking for", "alternative", "replace", "switching", "compare", "vs"])

    for kw in keywords:
        tokens = _keyword_tokens(kw)
        if not tokens:
            continue
        token_hits = sum(1 for t in tokens if t in text)
        if token_hits >= 1 and buyer_context and (pain_or_need or ask_context):
            return True
    return False

@router.post("/api/scan", response_model=List[Lead])
async def scan_leads(request: ScanRequest):
    """
    Scans Reddit for posts based on keywords, scores them with Gemini,
    saves to Couchbase, and returns the list of scored leads.
    """
    try:
        # 1. Fetch Reddit posts only
        search_keywords = _expand_keywords(request.keywords)
        raw_posts = await multi_scraper.fetch_all(
            search_keywords,
            limit_per_platform=2,
            platforms=["reddit"],
        )
        if not raw_posts:
            return []

        seen_urls: set = set()
        filtered_posts = []
        existing_matches = []
        for post in raw_posts:
            post_id = post.get("id")
            post_url = _normalize_url(post.get("url"))
            if not post_id or not post_url:
                continue

            if post_url in seen_urls:
                continue
            seen_urls.add(post_url)

            if _looks_like_noise(post.get("title"), post.get("body")):
                continue

            if not _matches_requested_problem(post.get("title"), post.get("body"), request.keywords):
                continue

            existing = couchbase_client.get_lead_by_id(str(post_id))
            if existing:
                if (
                    existing.get("status") not in {"discarded", "dismissed"}
                    and existing.get("signal_type") != "no_signal"
                    and int(existing.get("score", 0) or 0) >= 50
                ):
                    existing_matches.append(existing)
                continue

            filtered_posts.append(post)

        if not filtered_posts:
            existing_matches.sort(key=lambda x: x.get("score", 0), reverse=True)
            return existing_matches[:8]

        filtered_posts = filtered_posts[:8]

        # 2. Score ALL posts concurrently with Gemini
        analyses = await asyncio.gather(
            *[gemini_scorer.score_lead(post) for post in filtered_posts],
            return_exceptions=True
        )

        scored_leads = []
        for post, analysis in zip(filtered_posts, analyses):
            # Skip any posts that errored during scoring
            if isinstance(analysis, Exception):
                print(f"Scoring error for post {post.get('id')}: {analysis}")
                continue

            post_id = post.get("id")
            post_url = _normalize_url(post.get("url"))
            if not post_id or not post_url:
                continue

            score = int(analysis.get("lead_score", 0) or 0)
            signal_type = (analysis.get("signal_type") or "").strip()
            status = (analysis.get("status") or "").strip()
            analysis_error = (analysis.get("analysis_error") or "").strip()

            # Do not include or save NO-SIGNAL / discarded / failed-scoring results
            if analysis_error or signal_type == "no_signal" or status == "discarded" or score < 50:
                continue

            pretty_content = _format_post_content(post)

            lead = Lead(
                id=str(post_id),
                platform=post.get("platform") or "Social",
                source_url=post_url,
                content=_compact_text(pretty_content),
                author=str(post.get("author") or ""),
                timestamp=float(post.get("created_utc") or 0),
                keywords=request.keywords,
                score=score,
                signal_type=signal_type,
                urgency=analysis.get("urgency"),
                company_hint=analysis.get("company_hint"),
                role_hint=analysis.get("role_hint"),
                pain_point=analysis.get("pain_point"),
                outreach_draft=analysis.get("outreach_draft"),
                recommended_action=analysis.get("recommended_action"),
                analysis_error=analysis_error or None,
                status=status or "new"
            )

            # 3. Save to Couchbase
            couchbase_client.save_lead(lead.model_dump())
            scored_leads.append(lead)

        merged = {}
        for lead in existing_matches + [lead.model_dump() if hasattr(lead, "model_dump") else lead for lead in scored_leads]:
            lead_id = lead.get("id")
            if lead_id:
                merged[lead_id] = lead

        final_results = [l for l in merged.values() if str(l.get("platform") or "").lower() == "reddit"]
        final_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return final_results[:8]
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in scan_leads: {str(e).encode('ascii', 'ignore').decode('ascii')}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/leads", response_model=List[Lead])
async def get_leads(
    status: Optional[str] = Query(None, pattern="^(hot|warm|cold|discarded|in_pipeline|dismissed)$"),
):
    """
    Returns all leads from Couchbase sorted by lead_score descending.
    Optional filtering by status.
    """
    try:
        leads = couchbase_client.get_all_leads(status=status)
        required = {"id", "platform", "source_url", "content", "author", "timestamp", "keywords"}
        leads = [l for l in leads if isinstance(l, dict) and required.issubset(l.keys())]
        leads = [l for l in leads if str(l.get("platform") or "").lower() == "reddit"]
        if status is None:
            leads = [
                l for l in leads
                if (l.get("status") != "discarded")
                and (l.get("status") != "dismissed")
                and (l.get("signal_type") != "no_signal")
                and (int(l.get("score", 0) or 0) >= 50)
            ]
        leads.sort(key=lambda x: x.get("score", 0), reverse=True)
        return leads
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/leads/{lead_id}/push")
async def push_to_crm(lead_id: str):
    """
    Marks lead as 'in_pipeline' in Couchbase and sends it to the CRM via webhook.
    """
    lead_data = couchbase_client.get_lead_by_id(lead_id)
    if not lead_data:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Update status
    lead_data["status"] = "in_pipeline"
    couchbase_client.save_lead(lead_data)
    
    # Send to CRM Webhook
    webhook_url = os.getenv("CRM_WEBHOOK_URL")
    if webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json=lead_data)
        except Exception as e:
            print(f"Webhook failed: {e}")
            # We don't fail the request here, but ideally we'd log it
            
    return {"status": "success", "message": f"Lead {lead_id} pushed to CRM"}

@router.delete("/api/leads/{lead_id}")
async def dismiss_lead(lead_id: str):
    lead_data = couchbase_client.get_lead_by_id(lead_id)
    if not lead_data:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead_data["status"] = "dismissed"
    couchbase_client.save_lead(lead_data)
    return {"status": "success", "message": f"Lead {lead_id} dismissed"}

@router.get("/api/analytics")
async def get_analytics():
    """
    Returns high-level analytics for the dashboard.
    """
    all_leads = couchbase_client.get_all_leads(status=None)
    required = {"id", "platform", "source_url", "content", "author", "timestamp", "keywords"}
    all_leads = [l for l in all_leads if isinstance(l, dict) and required.issubset(l.keys())]
    all_leads = [l for l in all_leads if str(l.get("platform") or "").lower() == "reddit"]
    qualified = [
        l for l in all_leads
        if (l.get("status") != "discarded")
        and (l.get("status") != "dismissed")
        and (l.get("signal_type") != "no_signal")
        and (int(l.get("score", 0) or 0) >= 50)
    ]

    hot_count = sum(1 for l in qualified if l.get("status") == "hot")
    warm_count = sum(1 for l in qualified if l.get("status") == "warm")
    cold_count = sum(1 for l in qualified if l.get("status") == "cold")
    in_pipeline_count = sum(1 for l in qualified if l.get("status") == "in_pipeline")

    leads_by_platform: dict = {}
    for l in qualified:
        p = l.get("platform") or "unknown"
        leads_by_platform[p] = leads_by_platform.get(p, 0) + 1

    return {
        "total_leads": len(qualified),
        "hot_count": hot_count,
        "warm_count": warm_count,
        "cold_count": cold_count,
        "in_pipeline_count": in_pipeline_count,
        "leads_by_platform": leads_by_platform,
    }
