import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai.types import Content, Part
import json
import uuid
import logging

# Import centralized configuration and the main agent
import config
from agents.root_orchestrator import root_orchestrator_agent

# Dictionary to hold ADK resources
adk_resources = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup structured logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if not config.DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set.")
        
    logging.info("Loading ADK Runner and Database Session Service...")
    adk_resources["session_service"] = DatabaseSessionService(db_url=config.DATABASE_URL)
    adk_resources["runner"] = Runner(
        agent=root_orchestrator_agent,
        app_name=config.APP_NAME,
        session_service=adk_resources["session_service"]
    )
    yield
    logging.info("Cleaning up ADK resources...")
    adk_resources.clear()

app = FastAPI(
    title="Splunk Log Analysis Agent API",
    description="An API for interacting with a dynamic multi-agent system for log analysis.",
    version="2.5.0",
    lifespan=lifespan
)

async def event_generator(request: Request, user_id: str, session_id: str, user_query: str):
    runner = request.app.state.adk_resources["runner"]
    session_service = request.app.state.adk_resources["session_service"]

    try:
        await session_service.get_session(config.APP_NAME, user_id, session_id)
    except Exception:
        await session_service.create_session(config.APP_NAME, user_id, session_id=session_id)

    user_message = Content(parts=[Part(text=user_query)])
    
    async for event in runner.run_async(user_id, session_id, new_message=user_message):
        content_text = ""
        if event.content and event.content.parts:
            part = event.content.parts[0]
            if hasattr(part, 'text'):
                content_text = part.text
            else:
                try:
                    content_text = part.json()
                except AttributeError:
                    content_text = str(part)

        event_data = {
            "author": event.author,
            "is_final": event.is_final_response(),
            "content": content_text.strip()
        }
        yield f"data: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(0.1)

@app.post("/chat/stream")
async def stream_chat(request: Request, user_query: str, authorization: str | None = Header(default=None)):
    if not config.API_KEY or authorization != f"Bearer {config.API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    # In production, derive user and session IDs from a decoded JWT token.
    # This ensures each user has their own secure conversation history.
    # from my_auth import get_user_and_session_from_token
    # user_id, session_id = get_user_and_session_from_token(authorization)
    user_id = "authenticated_user_123" # Placeholder
    session_id = "session_for_user_123" # Placeholder

    return StreamingResponse(
        event_generator(request, user_id, session_id, user_query), 
        media_type="text/event-stream"
    )

@app.get("/")
def read_root():
    return {"message": "Splunk Agent API is running. POST to /chat/stream to interact."}

app.state.adk_resources = adk_resources