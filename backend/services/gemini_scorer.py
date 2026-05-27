from google import genai
from google.genai import types
import os
import json
from typing import Dict, Any
import re
from dotenv import load_dotenv

# Load environment variables if running standalone or early initialization
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

class GeminiScorer:
    def __init__(self):
        # Load API key from environment variable
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self.model_name = 'gemini-2.5-pro'
        else:
            self.client = None
            print("Warning: GEMINI_API_KEY not found in environment variables.")

    def _heuristic_analysis(self, post_obj: Dict[str, Any]) -> Dict[str, Any]:
        title = (post_obj.get("title") or "").strip()
        body = (post_obj.get("body") or "").strip()
        text = f"{title}\n{body}".lower()

        promo_markers = [
            "for hire", "hiring", "job opening", "free services", "portfolio",
            "i built", "launching", "check out", "my app", "my product",
            "top ", "best ", "list of", "companies", "agency", "development company", "development companies",
            "guide", "blog", "article", "case study", "newsletter", "webinar", "tutorial", "demo", "free trial",
        ]
        buyer_markers = [
            "i need", "we need", "my team", "our team", "looking for", "recommend", "any alternatives",
            "switching from", "replace", "replacing", "vs", "compare", "comparison", "?",
        ]
        if any(m in text for m in promo_markers) and not any(m in text for m in buyer_markers):
            return {
                "signal_type": "no_signal",
                "lead_score": 0,
                "urgency": "low",
                "company_hint": None,
                "role_hint": None,
                "pain_point": None,
                "outreach_draft": None,
                "recommended_action": "monitor",
                "status": "discarded",
            }

        dev_markers = [
            "stack trace", "traceback", "exception", "error:", "http 401", "http 403", "http 404", "http 500",
            "npm ", "pip ", "uvicorn", "fastapi", "react", "javascript", "typescript", "python", "api key",
            "sdk", "oauth", "token", "authentication", "unauthorized", "bug", "compile", "build failed",
        ]
        intent_markers = [
            "looking for", "recommend", "recommendation", "any alternatives", "alternative", "switching",
            "replace", "replacing", "vs", "compare", "comparison", "what tool", "what software", "best tool",
            "need a", "need an", "need help choosing",
        ]
        pain_markers = [
            "struggling", "problem", "issue", "pain", "manual", "slow", "expensive", "frustrat",
            "wasting time", "hard to manage", "hard to track", "missing leads", "can't keep up",
            "not working", "broken", "inefficient", "mess", "spreadsheet",
        ]
        category_markers = [
            "crm", "sales", "pipeline", "lead", "outreach", "dialer", "call", "cold email", "email outreach",
            "voice ai", "call ai", "sales ai", "contact tracking",
        ]
        urgent_markers = ["urgent", "asap", "immediately", "by tomorrow", "today", "right now"]

        has_intent = any(m in text for m in intent_markers) or ("need" in text) or ("looking" in text) or ("recommend" in text) or ("alternative" in text)
        has_category = any(m in text for m in category_markers)
        has_pain = any(m in text for m in pain_markers)
        looks_dev = any(m in text for m in dev_markers) and not (has_intent and has_category)

        buyer_pronouns = [" i ", " we ", " our ", " my ", " our team ", " my team "]
        has_buyer_voice = any(p in f" {text} " for p in buyer_pronouns)
        has_ask = ("?" in text) or ("recommend" in text) or ("looking for" in text) or ("any alternatives" in text) or ("what tool" in text) or ("which tool" in text)

        if looks_dev or not (has_category and (has_intent or has_pain)) or not (has_buyer_voice and (has_ask or has_pain or ("need " in text) or ("looking for" in text))):
            return {
                "signal_type": "no_signal",
                "lead_score": 0,
                "urgency": "low",
                "company_hint": None,
                "role_hint": None,
                "pain_point": None,
                "outreach_draft": None,
                "recommended_action": "monitor",
                "status": "discarded",
            }

        competitor_names = ["hubspot", "salesforce", "pipedrive", "apollo", "close", "zoho", "zendesk", "freshsales"]
        competitor = next((c for c in competitor_names if c in text), None)
        has_pain = has_pain or ("too expensive" in text) or ("hate" in text) or ("terrible" in text)
        is_urgent = any(m in text for m in urgent_markers)

        if not has_buyer_voice:
            return {
                "signal_type": "no_signal",
                "lead_score": 0,
                "urgency": "low",
                "company_hint": None,
                "role_hint": None,
                "pain_point": None,
                "outreach_draft": None,
                "recommended_action": "monitor",
                "status": "discarded",
            }

        if is_urgent:
            signal_type = "urgent_need"
            score = 90
            urgency = "high"
        elif competitor and has_pain:
            signal_type = "competitor_pain"
            score = 80
            urgency = "medium"
        elif any(m in text for m in ["vs", "compare", "comparison", "alternative", "switching", "replace", "replacing"]):
            signal_type = "active_evaluation"
            score = 78
            urgency = "medium"
        elif has_pain:
            signal_type = "advice_seeking"
            score = 72
            urgency = "medium"
        else:
            signal_type = "product_request"
            score = 75
            urgency = "low"

        if "recommend" in text or "looking for" in text:
            score += 8
        if "budget" in text or "affordable" in text or "pricing" in text:
            score += 5
        if is_urgent:
            score += 5
        score = max(0, min(100, score))

        if score < 50:
            status = "discarded"
        elif 50 <= score <= 69:
            status = "cold"
        elif 70 <= score <= 89:
            status = "warm"
        else:
            status = "hot"

        first_sentence = (re.split(r"(?<=[.!?])\s+", body.strip()) or [""])[0].strip()
        pain_point = first_sentence[:160] if first_sentence else title[:160]

        return {
            "signal_type": signal_type,
            "lead_score": int(score),
            "urgency": urgency,
            "company_hint": competitor.title() if competitor else None,
            "role_hint": None,
            "pain_point": pain_point or None,
            "outreach_draft": None,
            "recommended_action": "reply_to_post",
            "status": status,
        }

    def _extract_json(self, text: str) -> Dict[str, Any]:
        t = (text or "").strip()
        if "```json" in t:
            t = t.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in t:
            t = t.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            return json.loads(t)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", t)
            if not m:
                raise
            return json.loads(m.group(0))

    async def score_lead(self, post_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a social media post using Gemini to determine lead quality, intent, and actionable insights.
        """
        if not self.client:
            return self._heuristic_analysis(post_obj)

        title = post_obj.get("title", "")
        body = post_obj.get("body", "")
        subreddit = post_obj.get("subreddit", "")
        author = post_obj.get("author", "")

        system_prompt = (
            "You are a sales intelligence AI. Analyze this social media post to extract buying intent and lead details.\n\n"
            "Analyze the post's context, author's expression, and language to determine if it represents a potential business lead. "
            "You must categorize the lead signal type and calculate a lead score based on the following rules:\n\n"
            "--- SIGNAL TYPES & DEFINITIONS ---\n"
            "1. product_request: The user is explicitly asking for a product, tool, or service recommendation to solve a business problem.\n"
            "   - E.g. 'Looking for a CRM for a startup' or 'What sales call software do you recommend?'\n"
            "2. competitor_pain: The user is experiencing issues, frustration, or complaining about a specific competitor product.\n"
            "   - E.g. 'Hubspot is way too expensive for what it does' or 'Salesforce has a terrible UI and is super slow'\n"
            "3. active_evaluation: The user is actively comparing multiple tools or seeking direct feedback on a specific platform.\n"
            "   - E.g. 'Should I choose Close.com or Pipedrive for my outbound sales?' or 'Is anyone using Apollo.io? What are your thoughts?'\n"
            "4. advice_seeking: The user is asking for general business advice, strategies, or workflows in a relevant business area, but not explicitly asking for a tool yet.\n"
            "   - E.g. 'How do you handle your cold calling pipeline?' or 'What is the best way to clean email lists?'\n"
            "5. urgent_need: The user has a critical, immediate business pain point or system failure that needs an urgent solution.\n"
            "   - E.g. 'Our current outreach tool just banned our account. We need a replacement that can be live by tomorrow!'\n"
            "6. no_signal: The post does NOT present any lead opportunity. This category is a strict filter for noise and includes:\n"
            "   - Meta discussions, general industry news, articles, or blog shares.\n"
            "   - General chatter, career advice, job postings ('We are hiring'), or personal rants unrelated to buying software.\n"
            "   - Technical software developers asking coding, programming, or implementation questions (e.g. 'How to integrate Stripe in React?', 'Getting 401 error in Couchbase API', 'How to write a regex in Python').\n"
            "   - Spam, links, self-promotion, memes, or jokes.\n\n"
            "--- SCORING GUIDELINES ---\n"
            "- 90 to 100 (HOT Lead): Explicit, immediate buying interest. Asking for tool recommendations, active evaluation of competitor alternatives, or urgent needs.\n"
            "- 70 to 89 (WARM Lead): Clear pain point or competitor frustration, but not yet asking for vendor suggestions directly, or high-intent advice seeking.\n"
            "- 50 to 69 (COLD Lead): General advice seeking on workflows, high-level business strategy, or early-stage exploration without a specific problem.\n"
            "- 0 to 49 (NO LEAD/DISCARDED): Absolutely no intent, no relevance, technical coding/programming questions, meta discussions, or spam.\n\n"
            "--- CRITICAL GUARDRAIL ---\n"
            "If the post is a software developer/engineer asking a technical, programming, or coding/implementation question, you MUST categorize it as 'no_signal' and assign a 'lead_score' below 50. Do not treat developer technical queries as sales leads.\n\n"
            "--- OUTPUT FORMAT ---\n"
            "Provide your output as a JSON object with these EXACT keys. Do not add any markdown styling like ```json or any other text before/after the JSON.\n"
            "{\n"
            '  "signal_type": "product_request" | "competitor_pain" | "active_evaluation" | "advice_seeking" | "urgent_need" | "no_signal",\n'
            '  "lead_score": integer (0 to 100),\n'
            '  "urgency": "low" | "medium" | "high",\n'
            '  "company_hint": "string or null" (name of company they work for, or competitor mentioned),\n'
            '  "role_hint": "string or null" (e.g., Founder, SDR, Developer, Product Manager),\n'
            '  "pain_point": "A concise, one-sentence summary of their primary struggle or need.",\n'
            '  "outreach_draft": "A professional, personalized, and non-spammy outreach message (2-3 sentences) showing empathy for their specific pain point.",\n'
            '  "recommended_action": "reply_to_post" | "send_dm" | "linkedin_connect" | "monitor"\n'
            "}"
        )

        user_content = f"Title: {title}\nBody: {body}\nSubreddit: r/{subreddit}\nAuthor: u/{author}"

        try:
            # Call Gemini API using the new google-genai SDK
            generation_config = types.GenerateContentConfig(
                temperature=0.1,
                top_p=0.95,
                max_output_tokens=1024,
                response_mime_type="application/json",
            )

            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=f"{system_prompt}\n\nPost Content:\n{user_content}",
                config=generation_config,
            )
            
            # Clean and parse JSON response
            analysis = self._extract_json(response.text)
            
            # Determine status based on lead_score
            score = analysis.get("lead_score", 0)
            if score < 50:
                status = "discarded"
            elif 50 <= score <= 69:
                status = "cold"
            elif 70 <= score <= 89:
                status = "warm"
            else: # score >= 90
                status = "hot"
                
            analysis["status"] = status
            return analysis

        except Exception as e:
            print(f"Error scoring lead with Gemini: {e}")
            return self._heuristic_analysis(post_obj)

gemini_scorer = GeminiScorer()

async def main():
    """
    Test function for GeminiScorer running multiple scenarios
    """
    import asyncio
    
    scenarios = [
        {
            "name": "Scenario 1: High Intent CRM Recommendation Request (Should be HOT / product_request)",
            "post": {
                "title": "Need recommendations for a CRM for my startup",
                "body": "We are currently using spreadsheets but it's getting hard to manage leads. Looking for something affordable and easy to use.",
                "subreddit": "SaaS",
                "author": "startup_founder123"
            }
        },
        {
            "name": "Scenario 2: Competitor Pain / Alternative Search (Should be WARM or HOT / competitor_pain)",
            "post": {
                "title": "Hubspot is getting ridiculously expensive, any alternatives?",
                "body": "We are a small sales team of 4 people. HubSpot just raised our rates again. We only need simple pipeline management and contact tracking. What are you guys using?",
                "subreddit": "sales",
                "author": "sales_lead_alpha"
            }
        },
        {
            "name": "Scenario 3: Developer Technical Question (Should be DISCARDED / no_signal)",
            "post": {
                "title": "React Native Couchbase Lite sync gateway auth error 401",
                "body": "Hey guys, I am trying to authenticate my React Native app with Couchbase Sync Gateway. I followed the docs and configured the session cookie, but I keep getting a 401 unauthorized error. Here is my request code...",
                "subreddit": "reactnative",
                "author": "dev_juan"
            }
        },
        {
            "name": "Scenario 4: Meta/Career/Off-topic (Should be DISCARDED / no_signal)",
            "post": {
                "title": "How did you land your first role as an SDR?",
                "body": "I've been applying to roles for 3 months now with no luck. If anyone has tips on resume changes or how to stand out during interviews, I'd really appreciate it.",
                "subreddit": "sales",
                "author": "jobseeker99"
            }
        }
    ]
    
    print("--- Starting Gemini Scorer Comprehensive Test ---")
    for scenario in scenarios:
        print(f"\n==================================================")
        print(scenario["name"])
        print(f"==================================================")
        results = await gemini_scorer.score_lead(scenario["post"])
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
