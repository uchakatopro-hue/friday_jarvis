from dotenv import load_dotenv
import logging
import os
from typing import Optional, Dict, Any

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import noise_cancellation, google

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email
from api_client import get_api_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Agent configuration from environment
AGENT_NAME = os.getenv("AGENT_NAME", "Friday")
ENABLE_EXTERNAL_API_CALLS = os.getenv("ENABLE_EXTERNAL_API_CALLS", "true").lower() == "true"
INTERNAL_API_URL = os.getenv("INTERNAL_API_URL", "http://localhost:8000")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "")


class AssistantWithIntents(Agent):
    """
    Enhanced LiveKit Agent with intent detection and external API integration.
    
    Features:
    - Real-time audio processing with noise cancellation
    - Intent detection from user speech
    - Dynamic external API calls via FastAPI middleware
    - Interaction logging
    - Error handling and recovery
    """
    
    def __init__(self) -> None:
        """Initialize the enhanced assistant agent."""
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Aoede",
                temperature=0.7,
            ),
            tools=[
                get_weather,
                search_web,
                send_email,
            ],
        )
        self.api_client = None
        self.current_user_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        logger.info(f"Initialized {AGENT_NAME} agent with intent detection")
    
    async def initialize(self):
        """Initialize agent resources (async context)."""
        try:
            self.api_client = await get_api_client()
            logger.info("Agent API client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize API client: {e}")
    
    async def cleanup(self):
        """Cleanup agent resources."""
        if self.api_client:
            await self.api_client.close()
            logger.info("Agent API client cleaned up")
    
    async def handle_user_input(
        self,
        user_id: str,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Handle user input and detect intent.
        
        Args:
            user_id: User identifier
            text: User input text
            context: Optional context data
            
        Returns:
            Response from intent handler or model
        """
        self.current_user_id = user_id
        
        try:
            logger.info(f"User {user_id} input: {text[:100]}...")
            
            # Log interaction with FastAPI backend
            if self.api_client:
                await self.api_client.log_interaction(
                    user_id=user_id,
                    interaction_type="input",
                    content=text,
                    metadata={"context": context},
                )
            
            # Detect intent from user input
            intent_result = await self._detect_intent(text, context)
            
            if intent_result and ENABLE_EXTERNAL_API_CALLS:
                response = await self._handle_detected_intent(
                    user_id=user_id,
                    intent_result=intent_result,
                )
                return response
            
            # Log output interaction
            if self.api_client:
                await self.api_client.log_interaction(
                    user_id=user_id,
                    interaction_type="output",
                    content="Processing request...",
                )
            
            return "I'm processing your request. Please wait."
            
        except Exception as e:
            logger.error(f"Error handling user input: {e}")
            # Log error interaction
            if self.api_client:
                try:
                    await self.api_client.log_interaction(
                        user_id=user_id,
                        interaction_type="error",
                        content=f"Error: {str(e)}",
                    )
                except:
                    pass
            return f"I encountered an error: {str(e)}"
    
    async def _detect_intent(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Detect user intent from text input.
        
        Intents:
        - weather: Get weather for a location
        - search: Search the web
        - email: Send an email
        - context: Fetch user context
        - api_call: Make external API call
        
        Args:
            text: User input text
            context: Optional context
            
        Returns:
            Intent detection result or None
        """
        try:
            text_lower = text.lower()
            
            # Simple intent detection (can be enhanced with NLU)
            intent_keywords = {
                "weather": ["weather", "temperature", "forecast", "rain", "sunny"],
                "search": ["search", "find", "look up", "what is", "who is"],
                "email": ["email", "send message", "send email", "mail"],
                "context": ["context", "history", "previous", "remember"],
            }
            
            detected_intent = None
            for intent, keywords in intent_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    detected_intent = intent
                    break
            
            if detected_intent:
                logger.info(f"Intent detected: {detected_intent}")
                return {
                    "intent": detected_intent,
                    "confidence": 0.85,
                    "text": text,
                    "context": context,
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            return None
    
    async def _handle_detected_intent(
        self,
        user_id: str,
        intent_result: Dict[str, Any],
    ) -> str:
        """
        Handle detected intent by routing to appropriate handler.
        
        Args:
            user_id: User identifier
            intent_result: Intent detection result
            
        Returns:
            Response message
        """
        try:
            intent = intent_result.get("intent")
            
            logger.info(f"Handling intent '{intent}' for user {user_id}")
            
            # Notify backend of detected intent
            if self.api_client:
                await self.api_client.send_agent_event(
                    event_type="intent_detected",
                    data=intent_result,
                )
            
            # Route to handler
            handlers = {
                "weather": self._handle_weather_intent,
                "search": self._handle_search_intent,
                "email": self._handle_email_intent,
                "context": self._handle_context_intent,
            }
            
            handler = handlers.get(intent)
            if handler:
                return await handler(user_id, intent_result)
            
            return "Intent handler not found."
            
        except Exception as e:
            logger.error(f"Error handling detected intent: {e}")
            return f"Error handling intent: {str(e)}"
    
    async def _handle_weather_intent(
        self,
        user_id: str,
        intent_result: Dict[str, Any],
    ) -> str:
        """Handle weather intent."""
        logger.info("Processing weather intent")
        return "I can help you with weather. Which city would you like to know about?"
    
    async def _handle_search_intent(
        self,
        user_id: str,
        intent_result: Dict[str, Any],
    ) -> str:
        """Handle search intent."""
        logger.info("Processing search intent")
        return "I can search the web for you. What would you like me to search?"
    
    async def _handle_email_intent(
        self,
        user_id: str,
        intent_result: Dict[str, Any],
    ) -> str:
        """Handle email intent."""
        logger.info("Processing email intent")
        return "I can help you send an email. Please provide the recipient and message."
    
    async def _handle_context_intent(
        self,
        user_id: str,
        intent_result: Dict[str, Any],
    ) -> str:
        """Handle context intent."""
        try:
            if self.api_client:
                context = await self.api_client.fetch_context(user_id)
                logger.info(f"Fetched context for user {user_id}")
                return f"I found your context information: {str(context)[:200]}..."
            return "Unable to fetch context."
        except Exception as e:
            logger.error(f"Error handling context intent: {e}")
            return f"Error fetching context: {str(e)}"


async def entrypoint(ctx: agents.JobContext):
    """
    Agent entry point for LiveKit.
    
    Args:
        ctx: LiveKit job context with room and agent configuration
    """
    session = AgentSession()
    assistant = AssistantWithIntents()
    
    # Initialize agent
    await assistant.initialize()
    
    max_retries = 3
    retry_count = 0
    
    try:
        while retry_count < max_retries:
            try:
                logger.info(f"Starting agent session (attempt {retry_count + 1}/{max_retries})")
                
                await session.start(
                    room=ctx.room,
                    agent=assistant,
                    room_input_options=RoomInputOptions(
                        video_enabled=True,
                        noise_cancellation=noise_cancellation.BVC(),
                    ),
                )

                await ctx.connect()
                logger.info(f"{AGENT_NAME} agent session started successfully")
                break  # Success, exit retry loop
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Agent session error (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    import asyncio
                    wait_time = 5 * retry_count  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to start agent session after {max_retries} attempts")
                    raise

        # Run agent reply generation
        await session.generate_reply(instructions=SESSION_INSTRUCTION)
        
    finally:
        # Cleanup
        await assistant.cleanup()
        logger.info("Agent session cleanup completed")


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
