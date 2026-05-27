from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import os
import asyncio
from services.multi_platform_scraper import multi_scraper
from services.gemini_scorer import gemini_scorer
from services.couchbase_client import couchbase_client
from models.lead import Lead

router = APIRouter()

class ScanRequest(BaseModel):
    keywords: List[str]

def _compact_text(text: str, max_len: int = 420) -> str:
    if not text:
        return ""
    normalized = " ".join(str(text).split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1] + "…"

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

@router.post("/api/scan", response_model=List[Lead])
async def scan_leads(request: ScanRequest):
    """
    Scans Reddit for posts based on keywords, scores them with Gemini,
    saves to Couchbase, and returns the list of scored leads.
    """
    try:
        # 1. Fetch posts from ALL platforms concurrently
        raw_posts = await multi_scraper.fetch_all(request.keywords, limit_per_platform=2)
        if not raw_posts:
            return []

        # Cap to 8 posts max (2 per platform x 4 platforms)
        raw_posts = raw_posts[:8]

        # 2. Score ALL posts concurrently with Gemini
        analyses = await asyncio.gather(
            *[gemini_scorer.score_lead(post) for post in raw_posts],
            return_exceptions=True
        )

        scored_leads = []
        for post, analysis in zip(raw_posts, analyses):
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

            title         = post.get("title") or ""
            subreddit     = post.get("subreddit") or ""
            body          = post.get("body") or ""
            pretty_content = f"[r/{subreddit}] {title}\n\n{body}".strip()

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

        return scored_leads
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in scan_leads: {str(e).encode('ascii', 'ignore').decode('ascii')}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/leads", response_model=List[Lead])
async def get_leads(status: Optional[str] = Query(None, pattern="^(hot|warm|cold|discarded)$")):
    """
    Returns all leads from Couchbase sorted by lead_score descending.
    Optional filtering by status.
    """
    try:
        leads = couchbase_client.get_all_leads(status=status)
        required = {"id", "platform", "source_url", "content", "author", "timestamp", "keywords"}
        leads = [l for l in leads if isinstance(l, dict) and required.issubset(l.keys())]
        if status is None:
            leads = [
                l for l in leads
                if (l.get("status") != "discarded")
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

@router.get("/api/analytics")
async def get_analytics():
    """
    Returns high-level analytics for the dashboard.
    """
    analytics_data = couchbase_client.get_analytics()
    
    # Format the data for the frontend expectations
    by_status = analytics_data.get("by_status", {})
    by_platform = analytics_data.get("by_platform", {})
    
    total_leads = sum(by_status.values())
    
    analytics = {
        "total_leads": total_leads,
        "hot_count": by_status.get("hot", 0),
        "warm_count": by_status.get("warm", 0),
        "cold_count": by_status.get("cold", 0),
        "in_pipeline_count": by_status.get("in_pipeline", 0),
        "leads_by_platform": by_platform
    }
    return analytics
