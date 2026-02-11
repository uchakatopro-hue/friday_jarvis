from dotenv import load_dotenv
import logging
import os
import asyncio
import httpx

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    noise_cancellation,
)
from livekit.plugins import google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# Environment-configured values
AGENT_AUTH_TOKEN = os.getenv("AGENT_AUTH_TOKEN")
# Provide a safe default for local development
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL", "http://127.0.0.1:8000").strip()

if not AGENT_AUTH_TOKEN:
    logger.critical("CRITICAL: AGENT_AUTH_TOKEN not found in environment. Communication with FastAPI will fail.")

# HTTP client singleton for communicating with external FastAPI (Render)
_http_client: httpx.AsyncClient | None = None

async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        headers = {}
        if AGENT_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {AGENT_AUTH_TOKEN}"
        # Use EXTERNAL_API_URL as base if it looks valid (starts with http)
        if EXTERNAL_API_URL and EXTERNAL_API_URL.lower().startswith("http"):
            _http_client = httpx.AsyncClient(base_url=EXTERNAL_API_URL, headers=headers, timeout=10.0)
        else:
            # Don't set a base_url if EXTERNAL_API_URL is invalid; fallback to plain client
            _http_client = httpx.AsyncClient(headers=headers, timeout=10.0)
    return _http_client


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Aoede",
                temperature=0.7,
              # Set response timeout to 10 seconds for faster responses
            ),
            tools=[
                get_weather,
                search_web,
                send_email
            ],
        )
        


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"Starting agent session (attempt {retry_count + 1}/{max_retries})")

            # Ensure we connect to the room first so tracks get published (prevents infinite loading)
            try:
                await ctx.connect()
            except Exception as ce:
                logger.warning(f"ctx.connect() failed or timed out: {ce}. Continuing to attempt session start.")

            # Perform non-fatal health check of external API only if URL has a valid protocol
            api_url = EXTERNAL_API_URL or ""
            if api_url.lower().startswith("http"):
                try:
                    client = await get_http_client()
                    # Health endpoint; short timeout
                    resp = await client.get("/health", timeout=2.0)
                    if resp.status_code == 200:
                        logger.info("External FastAPI bridge is healthy")
                    else:
                        logger.warning(f"External FastAPI health returned {resp.status_code}; continuing.")
                except Exception as he:
                    logger.warning(f"Backend health check failed: {he}. Moving forward...")
            else:
                logger.warning("EXTERNAL_API_URL missing or invalid; skipping backend health check")

            # If LiveKit Cloud provides job assignment waiting, do it now (non-blocking for health check)
            if hasattr(ctx, "wait_for_assignment"):
                try:
                    logger.info("Waiting for job assignment from LiveKit Cloud...")
                    await ctx.wait_for_assignment()
                except Exception as wa:
                    logger.warning(f"wait_for_assignment failed or timed out: {wa}. Continuing.")

            # Start the agent session regardless of external API status
            await session.start(
                room=ctx.room,
                agent=Assistant(),
                room_input_options=RoomInputOptions(
                    video_enabled=True,
                    noise_cancellation=noise_cancellation.BVC(),
                ),
            )

            logger.info("Agent session started successfully")
            break  # Success, exit retry loop
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Agent session error: {e}")
            
            if retry_count < max_retries:
                import asyncio
                wait_time = 5 * retry_count  # Exponential backoff: 5s, 10s, 15s
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to start agent session after {max_retries} attempts")
                raise

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))