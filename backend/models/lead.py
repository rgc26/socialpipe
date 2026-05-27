from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class Lead(BaseModel):
    id: str
    platform: str = "reddit"
    source_url: str
    content: str
    author: str
    timestamp: float
    keywords: List[str]
    
    # Gemini Analysis Fields
    score: int = 0
    signal_type: Optional[str] = None
    urgency: Optional[str] = None
    company_hint: Optional[str] = None
    role_hint: Optional[str] = None
    pain_point: Optional[str] = None
    outreach_draft: Optional[str] = None
    recommended_action: Optional[str] = None
    analysis_error: Optional[str] = None
    
    # System status
    status: str = "new"  # discarded, cold, warm, hot, contacted, closed

class LeadCreate(BaseModel):
    platform: str
    source_url: str
    content: str
    author: str
    keywords: List[str]
