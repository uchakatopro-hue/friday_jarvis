import os
import uuid
import time
import logging
import subprocess
import sys
from typing import Optional, Any, Dict
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

from middleware import configure_cors, verify_agent_token, AGENT_AUTH_TOKEN
from api_client import get_api_client, cleanup_api_client

try:
    from livekit.api import AccessToken, VideoGrants
except ImportError:
    try:
        from livekit import AccessToken, VideoGrants
    except ImportError:
        try:
            from livekit.api import AccessToken
            from livekit.api import VideoGrants
        except ImportError:
            AccessToken = None
            VideoGrants = None

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to track agent process
agent_process = None

# Initialize FastAPI app
app = FastAPI(
    title="Friday - AI Voice Assistant",
    description="Personal AI voice assistant powered by LiveKit with external API integration",
    version="2.0.0",
)

# Configure CORS middleware
configure_cors(app)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# LiveKit configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# External API (FastAPI bridge) URL used by agents
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL")

# Validate LiveKit credentials
if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
    logger.error("Missing LiveKit credentials in .env file!")
    logger.error(f"  LIVEKIT_URL: {'✓' if LIVEKIT_URL else '✗'}")
    logger.error(f"  LIVEKIT_API_KEY: {'✓' if LIVEKIT_API_KEY else '✗'}")
    logger.error(f"  LIVEKIT_API_SECRET: {'✓' if LIVEKIT_API_SECRET else '✗'}")

# Agent configuration
AGENT_SESSION_TIMEOUT = int(os.getenv("AGENT_SESSION_TIMEOUT", "300"))  # 5 minutes default


# ====================== Pydantic Models ======================

class AgentEventRequest(BaseModel):
    """Request model for agent events."""
    event_type: str
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None


class AgentIntentRequest(BaseModel):
    """Request model for agent intent processing."""
    user_id: str
    intent: str
    parameters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class ExternalAPICallRequest(BaseModel):
    """Request model for external API calls."""
    endpoint: str
    method: str = "GET"
    params: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


class AgentInteractionLog(BaseModel):
    """Request model for logging agent interactions."""
    user_id: str
    interaction_type: str  # "input", "output", "tool_call", "error"
    content: str
    metadata: Optional[Dict[str, Any]] = None


# ====================== Lifecycle Events ======================

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    global agent_process
    
    logger.info("Starting Friday - AI Voice Assistant")
    logger.info(f" - LiveKit URL: {LIVEKIT_URL}")
    logger.info(f" - External API URL: {EXTERNAL_API_URL if EXTERNAL_API_URL else 'Not set'}")
    logger.info(f" - Agent Token Auth: {'Enabled' if AGENT_AUTH_TOKEN else 'Disabled'}")
    
    # Start agent in background
    try:
        logger.info("Starting LiveKit agent process...")
        # Get the Python executable from the current environment
        python_exe = sys.executable
        agent_process = subprocess.Popen(
            [python_exe, "agent.py", "console"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"Agent process started with PID: {agent_process.pid}")
    except Exception as e:
        logger.error(f"Failed to start agent process: {e}")
        logger.warning("Continuing without agent - web service will still work")
    
    # Initialize API client
    api_client = await get_api_client()
    logger.info(f"API client initialized with timeout: {api_client.timeout}s")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    global agent_process
    
    logger.info("Shutting down Friday - AI Voice Assistant")
    
    # Terminate agent process if running
    if agent_process:
        try:
            logger.info(f"Terminating agent process with PID: {agent_process.pid}")
            agent_process.terminate()
            # Wait for graceful shutdown, then kill if needed
            try:
                agent_process.wait(timeout=5)
                logger.info("Agent process terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Agent process did not terminate gracefully, killing...")
                agent_process.kill()
                agent_process.wait()
                logger.info("Agent process killed")
        except Exception as e:
            logger.error(f"Error terminating agent process: {e}")
    
    await cleanup_api_client()
    logger.info("API client resources cleaned up")


# ====================== Public Endpoints ======================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/create-room")
async def create_room():
    """Create a new LiveKit room"""
    try:
        room_name = f"room-{str(uuid.uuid4())[:8]}"
        logger.info(f"Created room: {room_name}")
        return {
            "success": True,
            "room_name": room_name,
            "livekit_url": LIVEKIT_URL
        }
    except Exception as e:
        logger.error(f"Error creating room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")


@app.get("/join-room/{room_name}", response_class=HTMLResponse)
async def join_room(request: Request, room_name: str):
    """Serve room interface"""
    return templates.TemplateResponse("room.html", {
        "request": request,
        "room_name": room_name,
        "livekit_url": LIVEKIT_URL
    })


@app.get("/token")
async def get_token(roomName: str = None, identity: str = None):
    """Generate LiveKit access token for client"""
    try:
        if not roomName:
            raise HTTPException(status_code=400, detail="roomName parameter is required")

        room_name = roomName
        if not identity:
            identity = f'user-{uuid.uuid4().hex[:8]}'

        # Try to import and use LiveKit token generation
        if AccessToken is not None and VideoGrants is not None:
            # Use proper LiveKit API
            token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            token.identity = identity
            token.name = identity

            # Grant permissions
            grant = VideoGrants()
            grant.room = room_name
            grant.room_join = True
            grant.can_publish = True
            grant.can_subscribe = True
            grant.can_publish_data = True

            token.video_grants = grant

            jwt_token = token.to_jwt()
            return {"token": jwt_token}
        else:
            # Fallback: return a mock token for testing
            import base64
            import json

            header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
            payload = base64.b64encode(json.dumps({
                "identity": identity,
                "name": identity,
                "room": room_name,
                "exp": int(time.time()) + 3600
            }).encode()).decode()

            signature = base64.b64encode(f"mock_signature_{room_name}_{identity}".encode()).decode()
            mock_token = f"{header}.{payload}.{signature}"
            logger.warning("Using mock token - LiveKit imports failed")
            return {"token": mock_token, "warning": "Mock token - LiveKit integration incomplete"}

    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Friday AI Assistant",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "livekit_url": LIVEKIT_URL,
        "external_api_url": EXTERNAL_API_URL,
        "agent_running": bool(agent_process)
    }


@app.get("/api/config")
async def get_config():
    """Get client configuration"""
    return {
        "livekit_url": LIVEKIT_URL,
        "agent_available": True,
        "features": {
            "voice_assistant": True,
            "weather_lookup": True,
            "web_search": True,
            "email_sending": bool(os.getenv("GMAIL_USER")),
            "video_support": True,
            "external_api_integration": True
        },
        "external_api_url": EXTERNAL_API_URL,
        "session_timeout": AGENT_SESSION_TIMEOUT
    }


# ====================== Agent Integration Endpoints (Authenticated) ======================

@app.post("/agent/event")
async def agent_event(
    request: AgentEventRequest,
    token: str = Depends(verify_agent_token),
) -> Dict[str, Any]:
    """
    Receive events from the LiveKit agent.
    Requires valid agent authentication token.
    
    Event types:
    - session_started: Agent session initialized
    - intent_detected: User intent detected with parameters
    - tool_called: Tool/function invoked by agent
    - response_generated: Agent generated response
    - error: Error occurred during processing
    - session_ended: Agent session terminated
    """
    try:
        logger.info(f"Agent event received: {request.event_type}")
        logger.debug(f"Event data: {request.data}")
        
        # Process event based on type
        if request.event_type == "intent_detected":
            logger.info(f"Intent detected: {request.data.get('intent')}")
            # Could trigger external integrations here
            
        elif request.event_type == "error":
            logger.error(f"Agent error: {request.data.get('message')}")
        
        return {
            "success": True,
            "message": f"Event {request.event_type} processed",
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error processing agent event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/intent")
async def process_intent(
    request: AgentIntentRequest,
    token: str = Depends(verify_agent_token),
) -> Dict[str, Any]:
    """
    Process agent-detected intent and route to appropriate handlers.
    Requires valid agent authentication token.
    """
    try:
        logger.info(f"Processing intent: {request.intent} for user: {request.user_id}")
        
        api_client = await get_api_client()
        
        # Log interaction
        await api_client.log_interaction(
            user_id=request.user_id,
            interaction_type="intent",
            content=request.intent,
            metadata={
                "parameters": request.parameters,
                "context": request.context,
            }
        )
        
        # Handle specific intents
        intent_handlers = {
            "fetch_context": lambda: _handle_fetch_context(request.user_id),
            "log_interaction": lambda: _handle_log_interaction(request.user_id, request.data),
            # Add more handlers as needed
        }
        
        handler = intent_handlers.get(request.intent)
        if handler:
            result = await handler()
        else:
            result = {"message": "Intent handler not found"}
        
        return {
            "success": True,
            "intent": request.intent,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error processing intent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/call-api")
async def agent_call_external_api(
    request: ExternalAPICallRequest,
    token: str = Depends(verify_agent_token),
) -> Dict[str, Any]:
    """
    Allow agent to call external APIs through this endpoint.
    Requires valid agent authentication token.
    
    This acts as a secure proxy for agent API calls.
    """
    try:
        logger.info(f"Agent requesting external API: {request.method} {request.endpoint}")
        
        api_client = await get_api_client()
        
        response = await api_client.call_endpoint(
            endpoint=request.endpoint,
            method=request.method,
            data=request.data,
            headers=request.headers,
            params=request.params,
        )
        
        return {
            "success": True,
            "endpoint": request.endpoint,
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error calling external API: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent/context/{user_id}")
async def get_user_context(
    user_id: str,
    token: str = Depends(verify_agent_token),
) -> Dict[str, Any]:
    """
    Fetch user context for the agent (recent interactions, preferences, etc.).
    Requires valid agent authentication token.
    """
    try:
        logger.info(f"Fetching user context for: {user_id}")
        
        api_client = await get_api_client()
        context = await api_client.fetch_context(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error fetching user context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/interactions/log")
async def log_interaction(
    request: AgentInteractionLog,
    token: str = Depends(verify_agent_token),
) -> Dict[str, Any]:
    """
    Log user-agent interactions for history and analytics.
    Requires valid agent authentication token.
    """
    try:
        logger.info(f"Logging interaction for user: {request.user_id}")
        
        api_client = await get_api_client()
        result = await api_client.log_interaction(
            user_id=request.user_id,
            interaction_type=request.interaction_type,
            content=request.content,
            metadata=request.metadata,
        )
        
        return {
            "success": True,
            "interaction_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== Internal Helper Functions ======================

async def _handle_fetch_context(user_id: str) -> Dict[str, Any]:
    """Handler for fetch_context intent."""
    api_client = await get_api_client()
    return await api_client.fetch_context(user_id)


async def _handle_log_interaction(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for log_interaction intent."""
    api_client = await get_api_client()
    return await api_client.log_interaction(
        user_id=user_id,
        interaction_type=data.get("type", "unknown"),
        content=data.get("content", ""),
        metadata=data.get("metadata"),
    )


# ====================== Error Handlers ======================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with logging."""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ====================== Entry Point ======================

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 7860))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )