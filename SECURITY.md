# Security Policy for Friday AI Assistant

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please email security@example.com instead of using the issue tracker.

## Sensitive Data Protection

### Never Commit
- `.env` files with credentials
- API keys or tokens
- Database passwords
- OAuth secrets
- Gmail app passwords
- Any sensitive configuration

### Always Use
- `.env.example` as template with placeholder values
- Render environment variables for production secrets
- GitHub Secrets for CI/CD credentials
- Secure secret management tools

## Secrets Already Exposed (January 2024)

The following credentials were accidentally committed and should be **regenerated**:
- GOOGLE_API_KEY: Regenerate at https://console.cloud.google.com/apis/credentials
- GOOGLE_CLIENT_ID/SECRET: Delete and create new at Google Cloud Console  
- GOOGLE_REFRESH_TOKEN: Re-authenticate to get new token
- GMAIL_APP_PASSWORD: Disable and create new at myaccount.google.com/apppasswords
- GMAIL_USER: No action needed
- LIVEKIT_API_KEY/SECRET: Regenerate at https://cloud.livekit.io
- OPENROUTER_API_KEY: Regenerate at https://openrouter.ai

**These have been removed from Git history using git-filter-repo.**

## Best Practices

1. **Before committing:**
   ```bash
   git diff --cached | grep -E "password|secret|key|token"
   ```

2. **Use pre-commit hooks:**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

3. **GitHub Secret Scanning:**
   - Enable in repository settings
   - Regenerate any exposed secrets immediately

4. **Render Deployment:**
   - Mark all secrets as "Secret" in environment variables
   - Never commit `.env` files
   - Use `.env.example` only with placeholder values

## Questions?

See [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for secure deployment instructions.
