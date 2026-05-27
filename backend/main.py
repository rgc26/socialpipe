from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

from routes import leads

app = FastAPI(
    title="SocialPipe API",
    description="Social Lead Generation Agent for Agora Hackathon 2026",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(leads.router)

@app.get("/")
async def root():
    return {"message": "SocialPipe API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
