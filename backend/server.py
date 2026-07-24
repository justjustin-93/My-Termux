from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL')
client = None
db = None
memory_status_checks: List[Dict[str, Any]] = []

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if mongo_url:
    try:
        client = AsyncIOMotorClient(mongo_url)
        db = client[os.environ.get('DB_NAME', 'mytermux')]
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("MongoDB unavailable, using in-memory fallback: %s", exc)
else:
    logger.warning("MONGO_URL is not set, using in-memory fallback")

# Create the main app without a prefix
app = FastAPI(title="MyTermux API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class ChatRequest(BaseModel):
    message: str

class ChatReply(BaseModel):
    reply: str
    suggestions: List[str]
    actions: List[str]

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "MyTermux API is live"}

@api_router.get("/overview")
async def overview():
    return {
        "status": "online",
        "agent": "MyTermux",
        "mode": "planning",
        "metrics": {
            "projects": 3,
            "sessions": 12,
            "tasks": 4,
            "health": "healthy",
        },
        "highlights": [
            "Local-first workflows",
            "Safe repair mode",
            "Fast project planning",
        ],
    }

@api_router.post("/chat", response_model=ChatReply)
async def chat(request: ChatRequest):
    text = request.message.lower().strip()
    if "scan" in text or "project" in text:
        reply = "I’m preparing a project scan and a follow-up plan that highlights the best next move."
        suggestions = ["Inspect the repo layout", "Check for open tasks", "Summarize current risks"]
        actions = ["Scan project", "Open tasks"]
    elif "sync" in text or "git" in text:
        reply = "Git sync is queued. I would review changed files first, then prepare a safe commit or pull path."
        suggestions = ["Review uncommitted changes", "Create a commit message", "Pull latest updates"]
        actions = ["Review changes", "Sync repo"]
    elif "media" in text:
        reply = "The media vault is ready. I can help organize images, audio, exports, and linked assets."
        suggestions = ["List recent media", "Attach media to a session", "Organize by type"]
        actions = ["Open media vault", "Attach media"]
    elif "repair" in text or "fix" in text:
        reply = "A self-heal pass is ready. I’ll inspect local state, note any issues, and suggest the safest repair path."
        suggestions = ["Check diagnostics", "Rebuild the local workspace", "Back up config"]
        actions = ["Run repair", "Back up config"]
    else:
        reply = "I can help with project scans, git sync, media organization, or workspace repair. Tell me what you want to tackle next."
        suggestions = ["Scan the current project", "Sync changes", "Open the media vault"]
        actions = ["Scan project", "Sync git", "Open media"]

    return ChatReply(reply=reply, suggestions=suggestions, actions=actions)

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)

    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()

    if db is not None:
        _ = await db.status_checks.insert_one(doc)
    else:
        memory_status_checks.append(doc)

    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    if db is not None:
        status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
        for check in status_checks:
            if isinstance(check['timestamp'], str):
                check['timestamp'] = datetime.fromisoformat(check['timestamp'])
        return status_checks

    return [
        StatusCheck(client_name=check['client_name'], timestamp=datetime.fromisoformat(check['timestamp']))
        for check in memory_status_checks
    ]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    if client is not None:
        client.close()