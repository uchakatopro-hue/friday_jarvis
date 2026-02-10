"""
Async API Client for LiveKit Agent to communicate with external services.
Handles secure API calls with token authentication and error handling.
"""

import logging
import os
from typing import Any, Dict, Optional
import httpx
from enum import Enum

logger = logging.getLogger(__name__)


class APIEndpoint(str, Enum):
    """Pre-configured external API endpoints"""
    WEATHER = "weather"
    CRM = "crm"
    DATABASE = "database"
    AI_TOOLS = "ai_tools"
    CUSTOM = "custom"


class APIClient:
    """
    Async HTTP client for agent to call external APIs.
    Handles authentication, error handling, and request formatting.
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize API client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Number of retries for failed requests
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self.api_endpoints = self._load_endpoints()
    
    def _load_endpoints(self) -> Dict[str, str]:
        """Load API endpoints from environment variables."""
        return {
            "crm_base_url": os.getenv("CRM_API_URL", ""),
            "database_base_url": os.getenv("DATABASE_API_URL", ""),
            "ai_tools_base_url": os.getenv("AI_TOOLS_API_URL", ""),
            "internal_api_url": os.getenv("INTERNAL_API_URL", "http://localhost:8000"),
        }
    
    async def initialize(self):
        """Initialize async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            logger.info("API client initialized")
    
    async def close(self):
        """Close async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("API client closed")
    
    async def call_endpoint(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an async HTTP request to an endpoint.
        
        Args:
            endpoint: API endpoint URL
            method: HTTP method (GET, POST, PUT, DELETE)
            data: JSON payload
            headers: Custom headers
            params: Query parameters
            
        Returns:
            Response JSON as dict
            
        Raises:
            APIClientError: If request fails
        """
        if self._client is None:
            await self.initialize()
        
        try:
            # Prepare headers with auth token if available
            request_headers = self._prepare_headers(headers)
            
            logger.debug(f"Calling {method} {endpoint}")
            
            response = await self._client.request(
                method=method,
                url=endpoint,
                json=data,
                headers=request_headers,
                params=params,
            )
            
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"API response received from {endpoint}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"API request failed: {e.response.status_code} - {e.response.text}")
            raise APIClientError(f"API error: {e.response.status_code}", response=e.response)
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise APIClientError(f"Request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in API call: {e}")
            raise APIClientError(f"Unexpected error: {str(e)}")
    
    async def call_internal_api(
        self,
        path: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Call an internal FastAPI endpoint.
        
        Args:
            path: API path (e.g., "/agent/intent")
            method: HTTP method
            data: JSON payload
            **kwargs: Additional arguments
            
        Returns:
            Response JSON
        """
        base_url = self.api_endpoints["internal_api_url"]
        endpoint = f"{base_url}{path}"
        return await self.call_endpoint(endpoint, method=method, data=data, **kwargs)
    
    async def send_agent_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send an event from the agent to the FastAPI backend.
        
        Args:
            event_type: Type of event (e.g., "intent_detected", "error")
            data: Event payload
            
        Returns:
            Server response
        """
        payload = {
            "event_type": event_type,
            "data": data,
        }
        return await self.call_internal_api(
            "/agent/event",
            method="POST",
            data=payload,
        )
    
    async def fetch_context(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch user context from internal API (e.g., recent interactions, preferences).
        
        Args:
            user_id: User identifier
            
        Returns:
            User context dict
        """
        return await self.call_internal_api(
            f"/user/{user_id}/context",
            method="GET",
        )
    
    async def log_interaction(
        self,
        user_id: str,
        interaction_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Log an agent-user interaction.
        
        Args:
            user_id: User identifier
            interaction_type: Type of interaction (input/output/tool_call)
            content: Interaction content
            metadata: Additional metadata
            
        Returns:
            Server response
        """
        payload = {
            "user_id": user_id,
            "type": interaction_type,
            "content": content,
            "metadata": metadata or {},
        }
        return await self.call_internal_api(
            "/interactions/log",
            method="POST",
            data=payload,
        )
    
    def _prepare_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Prepare request headers with authentication.
        
        Args:
            custom_headers: Custom headers to include
            
        Returns:
            Headers dict with auth token
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LiveKit-Agent/1.0",
        }
        
        # Add API authentication token if available
        api_token = os.getenv("INTERNAL_API_TOKEN")
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        
        # Merge custom headers
        if custom_headers:
            headers.update(custom_headers)
        
        return headers


class APIClientError(Exception):
    """Exception raised by API client."""
    
    def __init__(self, message: str, response: Optional[httpx.Response] = None):
        super().__init__(message)
        self.response = response
        self.status_code = response.status_code if response else None
        self.response_text = response.text if response else None


# Singleton instance
_client_instance: Optional[APIClient] = None


async def get_api_client() -> APIClient:
    """Get or create API client singleton."""
    global _client_instance
    if _client_instance is None:
        _client_instance = APIClient()
        await _client_instance.initialize()
    return _client_instance


async def cleanup_api_client():
    """Clean up API client resources."""
    global _client_instance
    if _client_instance:
        await _client_instance.close()
        _client_instance = None
