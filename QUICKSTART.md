# Quick Start Guide: LiveKit Agent + FastAPI Integration

## For Local Development (5 minutes)

### Step 1: Install Dependencies
```bash
# Create or activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### Step 2: Configure Environment
```bash
# Copy and edit environment file
cp .env.example .env

# Edit .env with your credentials:
# - LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
# - GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
# - GMAIL_USER, FROM_NAME
# - Generate INTERNAL_API_TOKEN (e.g., python -c "import secrets; print(secrets.token_urlsafe(32))")
```

**Note:** If you need to generate a new Google refresh token:
```bash
python get_google_refresh_token.py
```

### Step 3: Start Services

**Terminal 1 - FastAPI Server:**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Output should show:
```
Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Terminal 2 - LiveKit Agent (after server starts):**
```bash
python agent_enhanced.py
```

Output should show:
```
INFO:root:Initialized Friday agent with intent detection
INFO:root:Agent API client initialized
```

### Step 4: Test the Integration

**Test API Health:**
```bash
curl http://localhost:8000/health
```

**Test Agent Event (with auth token):**
```bash
curl -X POST http://localhost:8000/agent/event \
  -H "Authorization: Bearer YOUR_INTERNAL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "intent_detected",
    "data": {"intent": "search", "query": "Python async"}
  }'
```

**Expected response:**
```json
{
  "success": true,
  "message": "Event intent_detected processed",
  "timestamp": "2026-02-10T..."
}
```

---

## For Render Deployment (10 minutes)

### Step 1: Prepare Repository

```bash
# Ensure .env is in .gitignore
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore

# Stage changes
git add .
git commit -m "Add LiveKit + FastAPI integration with enhanced agent"
```

### Step 2: Create Render Service

1. Go to [render.com](https://render.com)
2. Sign in or create account
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Environment**: Docker
   - **Region**: Choose closest to users
   - **Plan**: Free or Starter

### Step 3: Set Environment Variables on Render

In Render dashboard, add these environment variables:

```
LIVEKIT_URL=wss://your-livekit-server.cloud
LIVEKIT_API_KEY=your-key
LIVEKIT_API_SECRET=your-secret
GOOGLE_CLIENT_ID=your-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
GMAIL_USER=your-email@gmail.com
FROM_NAME=Friday Assistant
AGENT_NAME=Friday
ENABLE_EXTERNAL_API_CALLS=true
INTERNAL_API_URL=https://your-render-app.onrender.com
INTERNAL_API_TOKEN=generate-strong-random-token
ALLOWED_ORIGINS=https://your-render-app.onrender.com,https://your-domain.com
PORT=10000
LOG_LEVEL=INFO
DEBUG_MODE=false
```

**Generate strong INTERNAL_API_TOKEN:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: Deploy

```bash
git push origin main
```

Render automatically deploys on push. Check deployment status in Render dashboard.

**Deployment complete when:**
- Service shows "Live"
- Logs show: "Application startup complete"

### Step 5: Verify Deployment

```bash
# Test health endpoint
curl https://your-render-app.onrender.com/health

# Test agent event
curl -X POST https://your-render-app.onrender.com/agent/event \
  -H "Authorization: Bearer YOUR_INTERNAL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "session_started", "data": {}}'
```

---

## Module Overview

### New Files Created

| File | Purpose | Usage |
|------|---------|-------|
| `api_client.py` | Async HTTP client for agent | Import: `from api_client import get_api_client` |
| `middleware.py` | Auth, CORS, rate limiting | Import: `from middleware import configure_cors` |
| `agent_enhanced.py` | Enhanced agent with intents | Run: `python agent_enhanced.py` |
| `app.py` (updated) | FastAPI with agent endpoints | Run: `uvicorn app:app` |
| `get_google_refresh_token.py` | OAuth2 token generation | Run: `python get_google_refresh_token.py` |
| `LIVEKIT_FASTAPI_INTEGRATION.md` | Full integration docs | Reference: Architecture, API docs |
| `.env.example` | Configuration template | Copy to `.env` and edit |

### Modified Files

| File | Changes |
|------|---------|
| `requirements.txt` | Added: fastapi, uvicorn, httpx, aiohttp, pydantic-settings |
| `app.py` | Added: CORS middleware, agent endpoints, auth, error handlers |
| `agent.py` | Kept for compatibility; use `agent_enhanced.py` for new features |
| `.env.example` | Comprehensive configuration guide |

---

## Key Features Implemented

### 1. Async API Client (`api_client.py`)
✅ Async HTTP requests with httpx
✅ Automatic authentication (Bearer token)
✅ Error handling and logging
✅ Singleton pattern for resource management
✅ Pre-configured internal API endpoints

### 2. Security & Middleware (`middleware.py`)
✅ CORS configuration
✅ Bearer token authentication
✅ Webhook signature verification
✅ Rate limiting (token bucket)
✅ Request logging

### 3. FastAPI Integration (`app.py`)
✅ Public endpoints (token, rooms, config)
✅ Authenticated agent endpoints
✅ Event routing
✅ Intent processing
✅ External API proxy
✅ Interaction logging
✅ Error handlers

### 4. Enhanced Agent (`agent_enhanced.py`)
✅ Intent detection
✅ Async API calls
✅ Interaction logging
✅ Error handling with recovery
✅ Context fetching
✅ Event communication

### 5. Configuration
✅ Comprehensive .env.example
✅ Environment variable validation
✅ Render deployment ready
✅ Docker support

---

## Troubleshooting

### Issue: "Invalid agent token"
**Solution:** Check `INTERNAL_API_TOKEN` matches in both `.env` and agent requests

### Issue: "Connection refused"
**Solution:** Ensure FastAPI server is running on correct port and URL

### Issue: "CORS error"
**Solution:** Add client origin to `ALLOWED_ORIGINS` in `.env` and restart server

### Issue: "Failed to obtain Google access token"
**Solution:** Run `python get_google_refresh_token.py` to refresh your token

### Issue: "Module not found"
**Solution:** Ensure requirements installed: `pip install -r requirements.txt`

---

## Architecture Diagram

```
Client (Web/Mobile)
    ↓ WebRTC
LiveKit Cloud
    ↓ Room Events
Agent (agent_enhanced.py)
    ↓ Async HTTP + Auth
FastAPI (app.py)
    ↓ Middleware: CORS, Auth, Logging
External APIs
```

---

## Endpoints Reference

### Public Endpoints
- `GET /` - Web UI
- `GET /health` - Health check
- `POST /create-room` - Create LiveKit room
- `GET /token` - Get access token
- `GET /api/config` - Get configuration

### Agent Endpoints (Require Auth)
- `POST /agent/event` - Log agent events
- `POST /agent/intent` - Process intents
- `GET /agent/context/{user_id}` - Get user context
- `POST /agent/call-api` - Proxy external API calls
- `POST /interactions/log` - Log interactions

---

## Next Steps

1. **Local Testing:** Start both servers and test endpoints
2. **Agent Customization:** Modify intent handlers in `agent_enhanced.py`
3. **External APIs:** Configure CRM, Database, or AI tool endpoints
4. **Deployment:** Push to GitHub and deploy to Render
5. **Monitoring:** Check logs and metrics in Render dashboard

---

## Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **LiveKit Python SDK:** https://docs.livekit.io/python-sdk/
- **HTTPX Docs:** https://www.python-httpx.org/
- **Render Guide:** https://render.com/docs
- **Google OAuth2:** https://developers.google.com/identity/protocols/oauth2

---

## Support

- Check logs: `see terminal output or docker logs`
- Review errors: Look for "ERROR" in logs
- Test with curl: Verify endpoints are accessible
- Read LIVEKIT_FASTAPI_INTEGRATION.md for detailed docs
