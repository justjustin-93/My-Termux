from fastapi import FastAPI, APIRouter
from starlette.concurrency import run_in_threadpool
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
import time
from typing import Optional

from mytermux.ai_integration import AIClient, AIClientError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import sentry_sdk


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL')
client = None
db = None
memory_status_checks: List[Dict[str, Any]] = []

# Prometheus metrics
AI_REQUESTS = Counter("ai_requests_total", "Total AI requests")
AI_ERRORS = Counter("ai_errors_total", "Total AI errors")
AI_LATENCY = Histogram("ai_latency_seconds", "AI request latency seconds")

# Initialize Sentry if configured (optional)
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    try:
        sentry_sdk.init(SENTRY_DSN)
    except Exception:
        logger.exception("Failed to initialize Sentry")

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
        # Use external AI service when available for open-ended queries.
        reply = "I can help with project scans, git sync, media organization, or workspace repair. Tell me what you want to tackle next."
        suggestions = ["Scan the current project", "Sync changes", "Open the media vault"]
        actions = ["Scan project", "Sync git", "Open media"]

        # Attempt to call configured AI endpoint for a richer reply.
        try:
            client = AIClient()
            payload = {"prompt": request.message}
            with AI_LATENCY.time():
                AI_REQUESTS.inc()
                resp = await client.send_request_async(payload)

            # Accept common shapes from adapters
            if isinstance(resp, dict):
                reply = resp.get("reply") or resp.get("result") or resp.get("text") or reply
                suggestions = resp.get("suggestions", suggestions)
                actions = resp.get("actions", actions)
        except AIClientError as exc:  # pragma: no cover - runtime behavior
            AI_ERRORS.inc()
            logger.warning("AI client error: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            AI_ERRORS.inc()
            logger.exception("Unexpected error calling AI client: %s", exc)

    return ChatReply(reply=reply, suggestions=suggestions, actions=actions)


@api_router.get("/metrics")
async def metrics():
    # Expose Prometheus metrics
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@api_router.post("/scan")
async def scan(target: Dict[str, Any]):
    """Request a project scan plan from the AI service for a given target.

    Payload example: {"target": "repo"}
    """
    try:
        client = AIClient()
        payload = {"prompt": f"Create a short actionable scan plan for {target.get('target', 'project')}"}
        resp = await client.send_request_async(payload)
        return resp
    except Exception as exc:
        logger.exception("Scan failed: %s", exc)
        raise

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