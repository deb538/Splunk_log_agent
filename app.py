import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
import os
from dotenv import load_dotenv
import json
import uuid

# Import the main orchestrator agent
from agents.root_orchestrator import root_orchestrator_agent

# Load environment variables for AWS credentials
load_dotenv()

# Dictionary to hold ADK resources
adk_resources = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load ADK resources on startup
    print("--- Loading ADK Runner and Session Service ---")
    APP_NAME = "dynamic_splunk_agent_app"
    adk_resources["session_service"] = InMemorySessionService()
    adk_resources["runner"] = Runner(
        agent=root_orchestrator_agent,
        app_name=APP_NAME,
        session_service=adk_resources["session_service"]
    )
    yield
    # Clean up resources on shutdown
    print("--- Cleaning up ADK resources ---")
    adk_resources.clear()

app = FastAPI(
    title="Splunk Log Analysis Agent API",
    description="An API for interacting with a dynamic multi-agent system for log analysis.",
    version="2.3.0",
    lifespan=lifespan
)

async def event_generator(request: Request, user_id: str, session_id: str, user_query: str):
    """This async generator yields events from the ADK runner in SSE format."""
    runner = request.app.state.adk_resources["runner"]
    session_service = request.app.state.adk_resources["session_service"]
    APP_NAME = runner.app_name

    try:
        await session_service.get_session(APP_NAME, user_id, session_id)
    except Exception:
        await session_service.create_session(APP_NAME, user_id, session_id=session_id)

    user_message = Content(parts=[Part(text=user_query)])
    
    async for event in runner.run_async(user_id, session_id, new_message=user_message):
        # The content of events from agents with output_schema will be the Pydantic object itself.
        # We need to serialize it for JSON streaming.
        content_text = ""
        if event.content and event.content.parts:
            part = event.content.parts[0]
            if hasattr(part, 'text'):
                content_text = part.text
            else: # It's likely a Pydantic model
                try:
                    content_text = part.json()
                except AttributeError:
                    content_text = str(part) # Fallback

        event_data = {
            "author": event.author,
            "is_final": event.is_final_response(),
            "content": content_text.strip()
        }
        yield f"data: {json.dumps(event_data)}\n\n"
        await asyncio.sleep(0.1)

@app.post("/chat/stream")
async def stream_chat(request: Request, user_query: str, authorization: str | None = Header(default=None)):
    """
    Accepts a user query and streams the agent's real-time events.
    """
    # In production, derive user and session IDs from the request,
    # for example, by decoding a JWT token from the Authorization header.
    # This makes the application multi-tenant and secure.
    if not authorization:
        # For demonstration, we'll create a new user/session if no token is provided.
        user_id = "guest_" + str(uuid.uuid4())
        session_id = "session_" + str(uuid.uuid4())
    else:
        # Placeholder for a real authentication function
        # from my_auth import get_user_and_session_from_token
        # user_id, session_id = get_user_and_session_from_token(authorization)
        user_id = "authenticated_user_123" # Dummy authenticated user
        session_id = "session_for_user_123"

    return StreamingResponse(
        event_generator(request, user_id, session_id, user_query), 
        media_type="text/event-stream"
    )

@app.get("/")
def read_root():
    return {"message": "Splunk Agent API is running. POST to /chat/stream to interact."}

app.state.adk_resources = adk_resources