# SocialPipe

![React](https://img.shields.io/badge/Frontend-React%2019-61DAFB?logo=react&logoColor=white)
![Vite](https://img.shields.io/badge/Build-Vite-646CFF?logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Language-Python%203.11+-3776AB?logo=python&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4?logo=google&logoColor=white)
![Couchbase](https://img.shields.io/badge/Database-Couchbase-EA2328?logo=couchbase&logoColor=white)
![Agora](https://img.shields.io/badge/Voice-Agora%20RTC-099DFD)
![Reddit](https://img.shields.io/badge/Source-Reddit%20Public%20Search-FF4500?logo=reddit&logoColor=white)

**SocialPipe**  
Reddit-first social lead generation for finding buyer-intent posts and turning them into qualified sales opportunities.

## 1. Project Name And Tagline

**Project Name:** SocialPipe  
**Tagline:** Turn Reddit conversations into qualified sales leads.

## 2. Problem Statement

Sales teams miss high-intent buyers because relevant conversations are scattered across public social platforms and are hard to monitor in real time. Manual prospecting is slow, noisy, and inconsistent, especially when teams need to identify people who are actively struggling with a problem and may become paying clients.

## 3. Solution Overview

SocialPipe scans public Reddit posts for buyer-intent keywords, filters out noise, and sends promising posts to Google Gemini for lead scoring and qualification. Qualified leads are stored in Couchbase and displayed in a lightweight dashboard and pipeline view for fast triage. The app is designed to help hackathon judges and sales users clearly see why a post is a possible lead, where it came from, and what action should happen next. The current branch is intentionally focused on Reddit-only lead capture to keep the demo stable and explainable.

## 4. Features List

- Reddit-first public lead discovery using the Reddit `search.json` endpoint
- Buyer-intent keyword expansion such as `need crm`, `replace crm`, and `crm too expensive`
- AI lead scoring and qualification with Google Gemini
- Noise filtering to remove promos, self-promotion, tutorials, listicles, and low-intent posts
- Lead quality thresholds so only qualified results are shown in the main feed
- Couchbase storage with lead persistence and analytics
- Dashboard with KPI cards, activity log, and live lead feed
- Pipeline view for detected, scored, qualified, and in-pipeline leads
- "Not a Fit" action to dismiss irrelevant leads so they do not keep resurfacing
- "Push to Pipeline" action to move leads into follow-up status
- CRM webhook push support for downstream automation
- Source-aware cards showing platform, hostname, and why the lead matched

## 5. Architecture Overview

```text
+---------------------+         +-----------------------+
| React + Vite UI     | <-----> | FastAPI Backend       |
| Dashboard / Pipeline|   HTTP  | /api/scan             |
+---------------------+         | /api/leads            |
                                | /api/analytics        |
                                +-----------+-----------+
                                            |
                                            v
                                +-----------------------+
                                | Reddit Public Search  |
                                | /search.json          |
                                +-----------+-----------+
                                            |
                                            v
                                +-----------------------+
                                | Lead Filtering        |
                                | Keyword expansion     |
                                | Noise removal         |
                                | Deduplication         |
                                +-----------+-----------+
                                            |
                                            v
                                +-----------------------+
                                | Google Gemini         |
                                | Score + qualify lead  |
                                +-----------+-----------+
                                            |
                           +----------------+----------------+
                           v                                 v
                +-----------------------+        +-----------------------+
                | Couchbase Capella     |        | CRM Webhook          |
                | Lead storage          |        | Optional push        |
                | Analytics             |        | to external CRM      |
                +-----------------------+        +-----------------------+
```

## 6. How Agora RTC SDK Is Integrated

Agora RTC was implemented as a **prototype voice layer** in an earlier version of the frontend using `agora-rtc-sdk-ng`.

Specific integration details:

- The frontend used `AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' })` to create a real-time audio client.
- The voice UI joined a fixed channel named `socialpipe-voice`.
- The frontend read `VITE_AGORA_APP_ID` from the frontend environment.
- On connect, the component called:
  - `client.join(APP_ID, CHANNEL, null, null)`
  - `AgoraRTC.createMicrophoneAudioTrack()`
  - `client.publish(localAudioTrack)`
- The RTC prototype exposed a floating mic button, connection state, and transcript panel.
- It also queried `/api/leads?status=hot` so the voice UI could speak lead summaries.

**Current repository status:** the active UI has been simplified to Reddit-only lead generation, and the voice assistant component has been removed from the current app shell for demo focus. The Agora RTC dependency remains in `frontend/package.json`, so the prototype can be restored if voice is reintroduced after judging.

## 7. How Agora Conversational AI Engine Is Integrated

Agora Conversational AI Engine is **not fully wired as a live production session in the current branch**. The original concept and prototype flow were:

- Use Agora RTC as the audio transport layer between the browser and a voice assistant session.
- Capture microphone audio from the frontend and stream it into an Agora-powered conversational experience.
- Let the assistant issue product-facing actions such as:
  - summarize hot leads
  - explain why a lead is qualified
  - trigger a new scan
  - read top pipeline items
- Return spoken responses plus visible transcript updates in the UI.

What exists today:

- A prior frontend prototype simulated the assistant response logic in the client and fetched lead summaries from the backend.
- Environment placeholders for Agora are still documented so the feature can be completed later.

For the hackathon demo, the shipped experience is currently the **Reddit lead intelligence workflow**, while Agora remains the intended voice interaction extension.

## 8. Setup Instructions

### Backend

1. Open a terminal and go to the backend folder:

   ```bash
   cd backend
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

3. Activate the virtual environment:

   ```bash
   .venv\Scripts\activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Create `backend/.env` based on the environment section below.

6. Start the API:

   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend

1. Open a second terminal and go to the frontend folder:

   ```bash
   cd frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Create `frontend/.env` based on the environment section below.

4. Start the frontend:

   ```bash
   npm run dev
   ```

## 9. Environment Variables Needed

### `backend/.env`

```env
# AI
GEMINI_API_KEY=your_gemini_api_key

# Couchbase
COUCHBASE_CONNECTION_STRING=couchbases://your-cluster-url
COUCHBASE_USERNAME=your_username
COUCHBASE_PASSWORD=your_password
COUCHBASE_BUCKET=socialpipe
COUCHBASE_CONFIG_PROFILE=wan_development

# CRM
CRM_WEBHOOK_URL=

# Optional / legacy Reddit vars
# Current Reddit scanner uses the public search endpoint and does not require OAuth.
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=SocialPipe/0.1

# Optional Agora placeholders for future voice re-enable
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=
```

### `frontend/.env`

```env
VITE_BACKEND_URL=http://localhost:8000

# Optional Agora placeholder for future voice re-enable
VITE_AGORA_APP_ID=
```

## 10. How To Run The Demo Locally

1. Start the backend on `http://localhost:8000`
2. Start the frontend with Vite
3. Open the frontend URL shown by Vite, typically `http://localhost:5173`
4. Enter a buyer-intent keyword such as:
   - `need crm`
   - `replace our crm`
   - `our current crm is too expensive`
   - `looking for a better way to manage leads`
5. Click **Run Scan**
6. Review qualified Reddit leads in the live feed
7. Open the original Reddit post using **View Post**
8. Move promising leads into the pipeline using **Push to Pipeline**
9. Dismiss bad matches using **Not a Fit**

## 11. Known Limitations

- The current branch is intentionally Reddit-only for demo reliability.
- Agora voice interaction is not active in the current UI even though the prototype and dependency work already started.
- Gemini scoring quality depends on API availability, quota, and prompt response quality.
- Public Reddit search can miss posts or return limited results for some phrases.
- Couchbase setup still depends on correct cluster access, credentials, and bucket configuration.
- The heuristic lead filter may still miss edge-case buyers or over-filter some legitimate prospects.
- CRM integration is webhook-based and assumes a receiving endpoint already exists.

## 12. Team Name

**Team Name:** SocialPipe

