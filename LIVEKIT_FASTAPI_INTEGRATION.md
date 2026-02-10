# LiveKit Agent + FastAPI Integration Guide

## Overview

This document covers the complete integration of a LiveKit Voice Agent with a custom FastAPI middleware for secure external API connectivity and deployment to Render.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client (Web/Mobile)                      │
└────────────────────┬────────────────────────────────────────┘
                     │ LiveKit Connection (WebRTC)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            LiveKit Cloud / Self-Hosted Server               │
└────────────────────┬────────────────────────────────────────┘
                     │ Room Events
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         LiveKit Voice Agent (agent_enhanced.py)              │
│  - Intent Detection                                          │
│  - Speech Processing                                         │
│  - Tool Invocation                                           │
└─────────────────┬──────────────────────────────────────────┘
                  │ HTTP Async Calls
                  ▼
┌─────────────────────────────────────────────────────────────┐
│    FastAPI Middleware (app.py) + Auth (middleware.py)       │
│  - CORS Configuration                                        │
│  - Token Authentication                                      │
│  - Event Routing                                             │
│  - External API Proxy                                        │
└─────────────────┬──────────────────────────────────────────┘
                  │ Async HTTP
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              External Services                               │
│  - CRM APIs        │ Database  │ AI Tools  │ Custom APIs    │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. API Client (`api_client.py`)

Async HTTP client for agent communication with external services.

**Features:**
- Asynchronous HTTP requests using `httpx`
- Token authentication
- Error handling and logging
- Singleton pattern for resource management
- Pre-configured internal API endpoints

**Usage:**
```python
from api_client import get_api_client

# Get client
api_client = await get_api_client()

# Call internal API
result = await api_client.call_internal_api(
    path="/agent/intent",
    method="POST",
    data={"intent": "weather", "location": "New York"}
)

# Log interaction
await api_client.log_interaction(
    user_id="user123",
    interaction_type="input",
    content="What's the weather?",
    metadata={"source": "voice"}
)

# Cleanup when done
await cleanup_api_client()
```

### 2. Middleware (`middleware.py`)

Authentication, CORS, and rate limiting for FastAPI.

**Features:**
- CORS configuration for cross-origin requests
- Bearer token authentication
- Request signature verification (webhooks)
- Rate limiting with token bucket algorithm
- Request logging

**Key Functions:**
- `configure_cors(app)`: Set up CORS middleware
- `verify_agent_token()`: Verify JWT/bearer token
- `verify_request_signature()`: Webhook signature validation
- `RateLimiter`: Rate limiting by IP/user

### 3. Enhanced FastAPI App (`app.py`)

FastAPI application with agent integration endpoints.

**Public Endpoints:**
- `GET /` - Web UI
- `POST /create-room` - Create LiveKit room
- `GET /token` - Get LiveKit access token
- `GET /health` - Health check
- `GET /api/config` - Configuration

**Agent Endpoints (Authenticated):**
- `POST /agent/event` - Receive agent events
- `POST /agent/intent` - Process detected intents
- `POST /agent/call-api` - Proxy external API calls
- `GET /agent/context/{user_id}` - Fetch user context
- `POST /interactions/log` - Log interactions

### 4. Enhanced Agent (`agent_enhanced.py`)

LiveKit agent with intent detection and async API calls.

**Features:**
- Intent detection from speech
- Async HTTP communication with FastAPI
- Interaction logging
- Error handling with recovery
- Configurable intent handlers

## Environment Configuration

Create a `.env` file with the following variables:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Google Configuration (for Gmail)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
GMAIL_USER=your-email@gmail.com

# Agent Configuration
AGENT_NAME=Friday
ENABLE_EXTERNAL_API_CALLS=true
AGENT_SESSION_TIMEOUT=300

# FastAPI Configuration
INTERNAL_API_URL=http://localhost:8000
INTERNAL_API_TOKEN=your-secure-agent-token
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:7860,https://your-domain.com

# External API Endpoints (Optional)
CRM_API_URL=https://api.crm-service.com
DATABASE_API_URL=https://api.database-service.com
AI_TOOLS_API_URL=https://api.ai-tools.com

# Server Configuration
PORT=7860
HTTP_TIMEOUT_SECONDS=30
WEBHOOK_SECRET=your-webhook-secret

# Additional Settings
FROM_NAME=Friday Assistant
LOG_LEVEL=INFO
```

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages added for integration:
- `fastapi` - Web framework
- `uvicorn[standard]` - ASGI server
- `httpx` - Async HTTP client
- `aiohttp` - Async HTTP utilities
- `python-multipart` - Form data handling
- `pydantic-settings` - Configuration management
- `cryptography` - Request signing

### 2. Configure Environment Variables

```bash
# Copy and customize the example
cp .env.example .env

# Edit with your credentials
nano .env
```

### 3. Local Development

**Terminal 1 - Start FastAPI Server:**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Start LiveKit Agent:**
```bash
python agent_enhanced.py
```

**Terminal 3 - (Optional) Run tests:**
```bash
python test_email.py
python test_agent_email.py
```

## Agent Integration with External APIs

### Intent Detection

The agent detects user intents from speech and routes to handlers:

```python
intent_keywords = {
    "weather": ["weather", "temperature", "forecast"],
    "search": ["search", "find", "look up"],
    "email": ["email", "send message"],
    "context": ["context", "history", "remember"],
}
```

### Handling Detected Intents

```python
async def _handle_weather_intent(self, user_id, intent_result):
    # Fetch context
    context = await self.api_client.fetch_context(user_id)
    
    # Call external API
    response = await self.api_client.call_endpoint(
        endpoint="https://api.weather.com/forecast",
        params={"location": intent_result.get("location")}
    )
    
    return f"Weather in {location}: {response['conditions']}"
```

### Calling FastAPI from Agent

```python
# Send event to FastAPI
await self.api_client.send_agent_event(
    event_type="intent_detected",
    data={"intent": "weather", "location": "NYC"}
)

# Call FastAPI endpoint
context = await self.api_client.call_internal_api(
    path="/agent/context/user123",
    method="GET"
)
```

### Authenticating Agent Requests

All agent requests to FastAPI must include the authentication token:

```python
headers = {
    "Authorization": f"Bearer {INTERNAL_API_TOKEN}",
    "Content-Type": "application/json",
}
```

The token is automatically included in `api_client.py`.

## Deployment to Render

### 1. Create Render Service

1. Go to [render.com](https://render.com)
2. Create a new "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Environment**: Docker
   - **Build Command**: (auto-detected from Dockerfile)
   - **Start Command**: (auto-detected)
   - **Port**: 7860 (or your PORT env var)

### 2. Environment Variables on Render

Add all variables from `.env.example` in Render dashboard:
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`
- `GMAIL_USER`
- `INTERNAL_API_TOKEN` (use a strong random string)
- `ALLOWED_ORIGINS` (comma-separated)

### 3. Dockerfile Configuration

The service uses Docker for deployment. Key files:
- `Dockerfile` - Container definition
- `render.yaml` - Render service configuration
- `Procfile` - Process definition

### 4. Deploy

```bash
git add .
git commit -m "Deploy LiveKit agent with FastAPI integration"
git push origin main
```

Render will automatically deploy on push.

## Testing

### Test Agent Event Handling

```bash
curl -X POST http://localhost:8000/agent/event \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "intent_detected",
    "data": {"intent": "weather", "location": "NYC"}
  }'
```

### Test Intent Processing

```bash
curl -X POST http://localhost:8000/agent/intent \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "intent": "search",
    "parameters": {"query": "python asyncio"}
  }'
```

### Test External API Call

```bash
curl -X POST http://localhost:8000/agent/call-api \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://api.example.com/data",
    "method": "GET",
    "params": {"id": "123"}
  }'
```

## Security Considerations

### 1. Token Management

- Use strong random tokens for `INTERNAL_API_TOKEN`
- Never commit `.env` to Git
- Rotate tokens regularly
- Use environment variables for all secrets

### 2. CORS Configuration

- Whitelist only trusted origins
- Use HTTPS in production
- Set `allow_credentials: true` only if needed

### 3. API Authentication

- All agent endpoints require valid token
- Token included in `Authorization` header
- Bearer token format: `Authorization: Bearer <token>`

### 4. External API Calls

- Validate endpoints before calling
- Use timeout for requests
- Log all API interactions
- Handle errors gracefully

### 5. Rate Limiting

- Enable rate limiting for public endpoints
- Implement token bucket algorithm
- Monitor rate limit violations

## Troubleshooting

### Agent Can't Connect to FastAPI

```
Check:
1. FastAPI server is running on correct port
2. INTERNAL_API_URL is correct in agent
3. INTERNAL_API_TOKEN matches between agent and FastAPI
4. Firewall allows connections
```

### Token Authentication Fails

```
Check:
1. INTERNAL_API_TOKEN in .env matches middleware.py
2. Authorization header format: "Bearer <token>"
3. Token is not expired
4. Check logs for "Invalid agent token"
```

### CORS Issues

```
Check:
1. Client origin is in ALLOWED_ORIGINS
2. Credentials are set correctly
3. Preflight requests (OPTIONS) are allowed
4. Use correct scheme (http/https)
```

### External API Call Fails

```
Check:
1. Endpoint URL is valid and accessible
2. Network connectivity
3. API authentication (if required)
4. Timeout not too short
5. Response format matches expectations
```

## Best Practices

### 1. Async/Await Pattern

Always use async/await for I/O operations:
```python
# Good
result = await api_client.call_endpoint(...)

# Bad - blocking
result = requests.get(...)  # Don't use synchronous requests
```

### 2. Error Handling

```python
try:
    result = await api_client.call_endpoint(...)
except APIClientError as e:
    logger.error(f"API error: {e}")
    # Handle gracefully
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Fallback behavior
```

### 3. Logging

Use structured logging for debugging:
```python
logger.info(f"Processing intent: {intent}")
logger.debug(f"Intent parameters: {params}")
logger.error(f"Failed to fetch context: {error}")
```

### 4. Resource Cleanup

Always cleanup async resources:
```python
try:
    api_client = await get_api_client()
    # ... use client
finally:
    await cleanup_api_client()
```

### 5. Testing

Create unit tests for handlers:
```python
async def test_weather_intent():
    agent = AssistantWithIntents()
    await agent.initialize()
    result = await agent._handle_weather_intent("user1", {...})
    assert "weather" in result.lower()
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LiveKit Python SDK](https://docs.livekit.io/python-sdk/)
- [HTTPX Documentation](https://www.python-httpx.org/)
- [Render Deployment Guide](https://render.com/docs)

## Support

For issues or questions:
1. Check logs: `docker logs <container-id>`
2. Review error messages
3. Check configuration
4. Test endpoints manually with curl/Postman
