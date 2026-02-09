# Friday AI Assistant - Render Deployment Guide

This guide walks you through deploying Friday on Render.com for production use.

## Prerequisites

- GitHub account with your Friday repository
- Render account (free tier available)
- LiveKit Cloud setup (API keys)
- Google Gemini API key
- Gmail credentials for email functionality

## Step 1: Prepare Your Repository

### 1.1 Ensure Required Files Exist

Your repository should contain:
```
friday_jarvis/
├── app.py
├── agent.py
├── tools.py
├── prompts.py
├── requirements.txt
├── Procfile
├── render.yaml
├── start.sh
├── static/
└── templates/
```

### 1.2 Update Requirements

Ensure `requirements.txt` includes all dependencies:

```
livekit-agents
livekit>=0.10.0
livekit-plugins-google
livekit-plugins-silero
livekit-plugins-noise-cancellation
fastapi
uvicorn[standard]
google-auth
google-auth-oauthlib
google-api-python-client
requests
python-dotenv
pydantic
gunicorn
websockets
```

### 1.3 Commit and Push

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

## Step 2: Set Up LiveKit Cloud

1. Visit [https://cloud.livekit.io](https://cloud.livekit.io)
2. Create an account and project
3. Generate API credentials:
   - Copy your LiveKit URL (format: `wss://xxx.livekit.cloud`)
   - Save `LIVEKIT_API_KEY`
   - Save `LIVEKIT_API_SECRET`

## Step 3: Get Google API Credentials

### 3.1 Gemini API Key

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create new API key
3. Copy `GOOGLE_API_KEY`
4. Enable the Gemini API in Google Cloud Console

### 3.2 Gmail Integration (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Gmail API
4. Create OAuth2 credentials (Web application)
5. Save:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`

6. For user authentication, generate a refresh token using:
```python
from google.auth.oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/gmail.send']
)
creds = flow.run_local_server(port=0)
print(creds.refresh_token)
```

Save the refresh token as `GOOGLE_REFRESH_TOKEN`.

## Step 4: Deploy on Render

### Option A: Using render.yaml (Recommended)

1. Go to [https://dashboard.render.com](https://dashboard.render.com)
2. Click "New +"
3. Select "Blueprint"
4. Paste your GitHub repository URL
5. Render will detect `render.yaml` and show configuration
6. Click "Deploy"

### Option B: Manual Configuration

1. Go to [https://dashboard.render.com](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:

   **General Settings**
   - Name: `friday-ai-assistant`
   - Region: Choose closest to your users
   - Branch: `main`
   - Root Directory: `.` (leave empty)

   **Build & Deploy**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Environment: `Python 3.11`

5. Click "Advanced" and add Environment Variables:

### Step 5: Set Environment Variables

In Render Dashboard, add these environment variables:

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret (Mark as Secret)
GOOGLE_REFRESH_TOKEN=your-refresh-token (Mark as Secret)
GMAIL_USER=your-email@gmail.com
FROM_NAME=Your Name or Company
FRIDAY_API_KEY=generate-a-secure-random-key (Mark as Secret)
ALLOWED_ORIGINS=https://your-domain.com,https://yourapp.com
PORT=10000
```

**Important**: Mark sensitive values as "Secret" in Render.

### Step 6: Deploy

1. Click "Create Service"
2. Render will automatically deploy
3. Wait for the build to complete (usually 2-5 minutes)
4. You'll get a URL like `https://friday-ai-assistant.onrender.com`

## Step 7: Verify Deployment

Test your deployment:

```bash
# Health check
curl https://your-render-url.onrender.com/health

# API configuration
curl -H "X-API-Key: your-api-key" \
     https://your-render-url.onrender.com/api/config

# Create a room
curl -X POST -H "X-API-Key: your-api-key" \
     https://your-render-url.onrender.com/create-room

# Get token
curl -H "X-API-Key: your-api-key" \
     "https://your-render-url.onrender.com/token?roomName=test&identity=user1"
```

## Step 8: Configure Custom Domain (Optional)

1. In Render Dashboard, go to your Web Service
2. Click "Settings"
3. Scroll to "Custom Domains"
4. Add your domain
5. Update DNS records with provided CNAME

## Step 9: Integrate with Web/Mobile Apps

Use your Render URL in your client applications:

**JavaScript:**
```javascript
const BASE_URL = 'https://friday-ai-assistant.onrender.com';
const API_KEY = 'your-friday-api-key';
```

**Swift:**
```swift
let baseURL = "https://friday-ai-assistant.onrender.com"
let apiKey = "your-friday-api-key"
```

**Kotlin:**
```kotlin
val baseURL = "https://friday-ai-assistant.onrender.com"
val apiKey = "your-friday-api-key"
```

## Troubleshooting

### Build Fails

1. Check build logs in Render Dashboard
2. Ensure all dependencies are in `requirements.txt`
3. Verify Python version compatibility (3.9+)

### Agent Not Starting

1. Check if agent.py has correct imports
2. Verify LIVEKIT credentials
3. Check agent logs: `tail -f /var/log/build.log`

### API Returns 403

- Verify `X-API-Key` header is correct
- Check `FRIDAY_API_KEY` environment variable is set

### Email Not Sending

1. Verify Gmail credentials are correct
2. Check if App Passwords are enabled (not 2FA)
3. Review tool error logs in Render dashboard

### Performance Issues

- Upgrade to Standard tier on Render
- Monitor memory usage in Render Dashboard
- Consider using background worker for agent

## Scaling Tips

1. **Use Background Workers**: Deploy agent as separate background worker
   - Keeps web server responsive
   - Separate resource allocation

2. **Enable Auto-scaling**: 
   - Render Pro feature
   - Scales based on CPU/memory

3. **Optimize Dependencies**:
   - Remove unused packages
   - Use lightweight alternatives

4. **Caching**:
   - Implement response caching
   - Reduce API calls to external services

## Monitoring

1. **Render Analytics**: Dashboard shows CPU, memory, requests
2. **Error Tracking**: Check build and deploy logs
3. **Uptime Monitoring**: Use external service like UptimeRobot
4. **Application Logs**: View real-time logs in Render Dashboard

## Maintenance

### Regular Updates

```bash
# Update dependencies
pip install --upgrade -r requirements.txt

# Commit and push
git commit -am "Update dependencies"
git push origin main
# Render auto-deploys on push (if configured)
```

### Backup

- GitHub is your backup
- Store API keys securely (never commit)
- Document any custom configuration

### Rollback

- Render stores deployment history
- Click "Deploy History" to rollback to previous version

## SSL/TLS

Render automatically provisions SSL certificates for:
- `your-service.onrender.com`
- Custom domains (automatic renewal)

## Cost Structure

**Free Tier:**
- Web services (with $5/month minimum after free allowance)
- Limited resources
- Suitable for testing

**Standard:**
- $12/month base
- More resources
- Better performance

**Pro:**
- Auto-scaling
- Priority support
- Team collaboration

## Next Steps

1. ✅ Deploy on Render
2. ✅ Test API endpoints
3. ✅ Integrate with web app (see CLIENT_SDK.md)
4. ✅ Integrate with iOS app (see CLIENT_SDK.md)
5. ✅ Integrate with Android app (see CLIENT_SDK.md)
6. ✅ Monitor performance
7. ✅ Optimize based on usage patterns

## Support & Resources

- Render Docs: https://render.com/docs
- Friday Documentation: See README.md
- SDK Examples: See CLIENT_SDK.md
- Issues: Check Render Dashboard logs

---

**Deployed on**: [Your Render URL]  
**Last Updated**: February 2024
