import asyncio
import os
import logging
from dotenv import load_dotenv
from livekit.plugins import google

async def test_gemini_live_connection():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in .env")
        return

    logger.info("Initializing RealtimeModel...")
    try:
        # Use the same model as in agent.py
        model = google.beta.realtime.RealtimeModel(
            voice="Aoede",
            temperature=0.7,
        )
        
        # We don't have a room context here, so we'll just try to see 
        # if the underlying client can be initialized and maybe 
        # a simple check can be performed.
        
        # Note: Actually connecting requires a full LiveKit session or 
        # direct use of the google-genai client.
        
        from google import genai
        client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
        
        logger.info("Attempting to list models as a connectivity check...")
        for m in client.models.list():
            if 'gemini' in m.name:
                logger.info(f"Found model: {m.name}")
        
        logger.info("Connectivity check (REST) successful.")
        
        # Now try a minimal websocket opening if possible
        # Realtime API is websocket based. 
        # This part is harder to test without full stream logic, 
        # but let's see if we can trigger the plugin's internal client.
        
        logger.info(" Gemini Live Handshake check is best performed via the agent itself with increased logging.")

    except Exception as e:
        logger.error(f"Connection test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini_live_connection())
